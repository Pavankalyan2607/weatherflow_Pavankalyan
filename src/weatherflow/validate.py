"""Data quality checks: row-level quarantine plus dataset-level fail/warn checks."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
KEY_COLUMNS = ["city", "observed_at_utc"]


class DataQualityError(Exception):
    """Raised when a blocking data quality check fails."""


@dataclass
class CheckResult:
    """Outcome of one data quality check."""

    name: str
    dimension: str
    severity: str  # "quarantine" | "fail" | "warn"
    passed: bool
    failed_rows: int
    details: str


def validate(
    df: pd.DataFrame, cfg: dict, incremental: bool = False
) -> tuple[pd.DataFrame, pd.DataFrame, list[CheckResult]]:
    """Run all checks. Returns (good_rows, quarantined_rows, results)."""
    dq = cfg["data_quality"]
    temp, hum = dq["temperature_c"], dq["humidity_pct"]
    df = df.reset_index(drop=True)
    results: list[CheckResult] = []
    reasons = np.full(len(df), "", dtype=object)

    def row_check(name: str, dimension: str, severity: str, bad, details: str) -> None:
        bad = np.asarray(bad, dtype=bool)
        n = int(bad.sum())
        results.append(CheckResult(name, dimension, severity, n == 0, n, details if n else "ok"))
        if severity == "quarantine":
            for i in np.flatnonzero(bad):
                reasons[i] += f"{name}; "

    # 1. Completeness (row, quarantine)
    row_check(
        "required_not_null", "Completeness", "quarantine",
        df[["city", "observed_at_utc", "temperature_c"]].isna().any(axis=1),
        "city, observed_at_utc or temperature_c is null",
    )
    # 2. Validity (row, quarantine)
    row_check(
        "temperature_in_range", "Validity", "quarantine",
        (df["temperature_c"] < temp["min"]) | (df["temperature_c"] > temp["max"]),
        f"temperature_c outside {temp['min']} to {temp['max']}",
    )
    # 3. Validity (row, quarantine)
    row_check(
        "humidity_in_range", "Validity", "quarantine",
        (df["humidity_pct"] < hum["min"]) | (df["humidity_pct"] > hum["max"]),
        f"humidity_pct outside {hum['min']} to {hum['max']}",
    )
    # 4. Validity (row, quarantine)
    row_check(
        "non_negative_precip_wind", "Validity", "quarantine",
        (df["precipitation_mm"] < 0) | (df["wind_speed_kmh"] < 0),
        "precipitation_mm or wind_speed_kmh is negative",
    )

    # 5. Uniqueness (dataset, fail)
    n_dup = int(df.duplicated(subset=KEY_COLUMNS, keep=False).sum())
    results.append(CheckResult(
        "no_duplicate_keys", "Uniqueness", "fail", n_dup == 0, n_dup,
        f"{n_dup} rows share a (city, observed_at_utc) key" if n_dup else "ok",
    ))

    # 6. Completeness (dataset, fail): every configured city has enough hours
    counts = df.groupby("city").size()
    short = {
        c["name"]: int(counts.get(c["name"], 0))
        for c in cfg["cities"]
        if counts.get(c["name"], 0) < dq["min_hours_per_city"]
    }
    results.append(CheckResult(
        "city_hour_coverage", "Completeness", "fail", not short, len(short),
        f"cities below {dq['min_hours_per_city']} hours: {short}" if short else "ok",
    ))

    # 7. Timeliness (dataset, warn, incremental runs only)
    if incremental:
        now = pd.Timestamp.now(tz="UTC")
        past = df.loc[df["observed_at_utc"] <= now, "observed_at_utc"]
        if past.empty:
            ok, detail = False, "no observations in the past"
        else:
            age_h = (now - past.max()).total_seconds() / 3600
            ok = age_h <= dq["max_staleness_hours"]
            detail = "ok" if ok else f"latest past observation is {age_h:.1f} hours old"
        results.append(CheckResult("data_is_fresh", "Timeliness", "warn", ok, 0 if ok else 1, detail))
    else:
        results.append(CheckResult(
            "data_is_fresh", "Timeliness", "warn", True, 0, "skipped (full run)"))

    # 8. Consistency (row, warn)
    row_check(
        "feels_like_close_to_temp", "Consistency", "warn",
        (df["feels_like_c"] - df["temperature_c"]).abs() > dq["feels_like_max_diff_c"],
        f"feels_like_c differs from temperature_c by more than {dq['feels_like_max_diff_c']}",
    )
    # 9. Validity (row, warn): unknown WMO weather code
    row_check(
        "weather_code_known", "Validity", "warn",
        df["weather_category"] == "unknown",
        "weather_code not found in the WMO lookup",
    )

    for r in results:
        if not r.passed:
            level = logging.ERROR if r.severity == "fail" else logging.WARNING
            logger.log(level, "DQ check failed [%s] %s: %s (%d rows)",
                       r.severity, r.name, r.details, r.failed_rows)

    flagged = np.array([bool(r) for r in reasons], dtype=bool)
    good = df[~flagged].reset_index(drop=True)
    bad = df[flagged].copy()
    bad["dq_failure_reason"] = [r.rstrip("; ") for r in reasons[flagged]]
    return good, bad, results


def raise_for_blocking(results: list[CheckResult]) -> None:
    """Stop the run if any blocking (fail) check did not pass."""
    failed = [r.name for r in results if r.severity == "fail" and not r.passed]
    if failed:
        logger.error("Blocking data quality checks failed: %s. Load stopped.", ", ".join(failed))
        raise DataQualityError(f"Blocking data quality checks failed: {', '.join(failed)}")


def write_quarantine(bad: pd.DataFrame, quarantine_dir: Path) -> Path | None:
    """Write quarantined rows (with dq_failure_reason) to a run_date folder."""
    if bad.empty:
        logger.info("No rows quarantined")
        return None
    now = datetime.now(timezone.utc)
    folder = Path(quarantine_dir) / f"run_date={now:%Y-%m-%d}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"part-{now:%Y%m%dT%H%M%S}.parquet"
    bad.to_parquet(path, index=False)
    logger.warning("Quarantined %d rows -> %s", len(bad), path)
    return path


def write_dq_report(
    results: list[CheckResult], total_rows: int, quarantined_rows: int, report_dir: str
) -> Path:
    """Write a markdown DQ summary for this run."""
    now = datetime.now(timezone.utc)
    folder = PROJECT_ROOT / report_dir
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{now:%Y%m%dT%H%M%S}.md"
    lines = [
        f"# Data quality report {now:%Y-%m-%d %H:%M:%S} UTC",
        "",
        f"- Rows checked: {total_rows}",
        f"- Rows quarantined: {quarantined_rows}",
        f"- Rows passed: {total_rows - quarantined_rows}",
        "",
        "| # | Check | Dimension | Severity | Result | Failed rows | Details |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        outcome = "PASS" if r.passed else "FAIL"
        lines.append(
            f"| {i} | {r.name} | {r.dimension} | {r.severity} | {outcome} | {r.failed_rows} | {r.details} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("DQ report written to %s", path)
    return path