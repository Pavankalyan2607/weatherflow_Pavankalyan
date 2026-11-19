"""Wire Extract, Transform, Validate and Load together."""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from weatherflow.config import load_config
from weatherflow.extract import extract, extract_backfill
from weatherflow.load import SOURCE_ARCHIVE, SOURCE_FORECAST, load, write_parquet
from weatherflow.lookups import load_wmo_codes
from weatherflow.transform import transform
from weatherflow.validate import (
    raise_for_blocking,
    validate,
    write_dq_report,
    write_quarantine,
)
from weatherflow.watermark import TS_FORMAT, compute_window, get_high_water_mark

logger = logging.getLogger(__name__)


def _process(raw: list, cfg: dict[str, Any], source: str, incremental: bool) -> int:
    """Shared Transform -> Validate -> Load path used by run and backfill."""
    ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    df = transform(raw, load_wmo_codes(), ingested_at)

    good, bad, results = validate(df, cfg, incremental=incremental)
    write_quarantine(bad, Path(cfg["paths"]["quarantine_dir"]))
    write_dq_report(results, len(df), len(bad), cfg["data_quality"]["report_dir"])
    raise_for_blocking(results)

    write_parquet(good, Path(cfg["paths"]["processed_dir"]))
    return load(good, Path(cfg["paths"]["database"]), cfg, source=source)


def build_windows(cfg: dict[str, Any], now_utc: datetime) -> dict:
    """Per city: the (start, end) dates to request, or None to fall back to past_days=1."""
    db_path = Path(cfg["paths"]["database"])
    overlap = cfg["incremental"]["overlap_hours"]
    windows = {}
    for city in cfg["cities"]:
        mark = get_high_water_mark(db_path, city["name"], SOURCE_FORECAST, now_utc)
        window = compute_window(mark, now_utc, overlap)
        windows[city["name"]] = window
        if window is None:
            logger.info("%s: nothing loaded yet, falling back to past_days=1", city["name"])
        else:
            logger.info("%s: high-water mark %s UTC, requesting %s to %s",
                        city["name"], mark.strftime(TS_FORMAT), window[0], window[1])
    return windows


def run() -> int:
    """Incremental run: fetch only what is new (plus the forecast). Returns rows loaded."""
    start = time.perf_counter()
    cfg = load_config()
    windows = build_windows(cfg, datetime.now(timezone.utc))
    raw = extract(cfg, windows)
    if not raw:
        logger.error("No data extracted, nothing to load")
        return 0
    rows = _process(raw, cfg, SOURCE_FORECAST, incremental=True)
    logger.info("Pipeline finished: %d rows in %.1fs", rows, time.perf_counter() - start)
    return rows


def resolve_backfill_range(
    cfg: dict[str, Any],
    days: int | None,
    start_date: date | None,
    end_date: date | None,
    today: date,
) -> tuple[date, date]:
    """Work out the date range. By default it ends lag_days before today."""
    latest_safe = today - timedelta(days=cfg["backfill"]["lag_days"])
    end = end_date or latest_safe
    if start_date is None:
        n = days or cfg["backfill"]["default_days"]
        start = end - timedelta(days=n - 1)
    else:
        start = start_date
    if start > end:
        raise ValueError(f"start date {start} is after end date {end}")
    if end > latest_safe:
        logger.warning("End date %s is newer than %s: the archive lags real time, "
                       "recent hours may be empty and get quarantined", end, latest_safe)
    return start, end


def backfill(
    days: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    """Load history from the archive API. Safe to re-run (idempotent upsert)."""
    start_time = time.perf_counter()
    cfg = load_config()
    start, end = resolve_backfill_range(
        cfg, days, start_date, end_date, datetime.now(timezone.utc).date()
    )
    logger.info("Backfill %s to %s", start, end)
    raw = extract_backfill(cfg, start, end)
    if not raw:
        logger.error("No data extracted, nothing to load")
        return 0
    rows = _process(raw, cfg, SOURCE_ARCHIVE, incremental=False)
    logger.info("Backfill finished: %d rows in %.1fs", rows, time.perf_counter() - start_time)
    return rows