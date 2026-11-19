"""Load step: star schema (dim_city, dim_date, fact_weather_hourly) in SQLite, plus Parquet."""
from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"
SOURCE = "open-meteo"
DEFAULT_COUNTRY = "United Kingdom"

FACT_COLUMNS = [
    "city_id", "date_id", "observed_at_utc", "hour_local",
    "temperature_c", "temperature_f", "feels_like_c", "humidity_pct",
    "precipitation_mm", "wind_speed_kmh", "wind_speed_ms", "beaufort_scale",
    "weather_code", "weather_description", "weather_category", "is_daylight",
    "outdoor_work_risk", "source", "ingested_at_utc",
]
FACT_KEY = ["city_id", "observed_at_utc", "source"]

_updates = ", ".join(f"{c} = excluded.{c}" for c in FACT_COLUMNS if c not in FACT_KEY)
FACT_UPSERT_SQL = (
    f"INSERT INTO fact_weather_hourly ({', '.join(FACT_COLUMNS)}) "
    f"VALUES ({', '.join(['?'] * len(FACT_COLUMNS))}) "
    f"ON CONFLICT (city_id, observed_at_utc, source) DO UPDATE SET {_updates}"
)

CITY_UPSERT_SQL = """
INSERT INTO dim_city (city_name, country, latitude, longitude)
VALUES (?, ?, ?, ?)
ON CONFLICT (city_name) DO UPDATE SET
    country = excluded.country,
    latitude = excluded.latitude,
    longitude = excluded.longitude
"""

DATE_INSERT_SQL = """
INSERT INTO dim_date
(date_id, full_date, year, quarter, month, month_name, day,
 day_of_week, day_of_week_num, is_weekend)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (date_id) DO NOTHING
"""


def build_dim_date(start, end) -> list[tuple]:
    """One row per calendar day from start to end (inclusive)."""
    days = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="D")
    return [
        (
            int(d.strftime("%Y%m%d")), d.strftime("%Y-%m-%d"), d.year, d.quarter,
            d.month, d.month_name(), d.day, d.day_name(), d.day_of_week + 1,
            int(d.day_of_week >= 5),
        )
        for d in days
    ]


def to_fact_rows(df: pd.DataFrame, city_ids: dict[str, int]) -> list[tuple]:
    """Turn the transformed frame into rows for fact_weather_hourly."""
    fact = df.copy()
    fact["city_id"] = fact["city"].map(city_ids)
    if fact["city_id"].isna().any():
        missing = sorted(fact.loc[fact["city_id"].isna(), "city"].unique())
        raise ValueError(f"Cities missing from dim_city: {missing}")
    fact["date_id"] = fact["observed_at_local"].dt.strftime("%Y%m%d").astype(int)
    fact["hour_local"] = fact["observed_at_local"].dt.hour
    fact["observed_at_utc"] = fact["observed_at_utc"].dt.strftime("%Y-%m-%dT%H:%M")
    fact["is_daylight"] = fact["is_daylight"].astype(int)
    fact["source"] = SOURCE
    out = fact[FACT_COLUMNS].astype(object)
    return list(out.where(out.notna(), None).itertuples(index=False, name=None))


def load(df: pd.DataFrame, db_path: Path, cfg: dict) -> int:
    """Upsert dimensions and facts in ONE transaction. Returns fact rows written."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    cities = [
        (c["name"], c.get("country", DEFAULT_COUNTRY), c["latitude"], c["longitude"])
        for c in cfg["cities"]
    ]
    dates = build_dim_date(cfg["dim_date"]["start"], cfg["dim_date"]["end"])
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        with conn:  # commits on success, rolls back on any exception
            conn.executemany(CITY_UPSERT_SQL, cities)
            conn.executemany(DATE_INSERT_SQL, dates)
            city_ids = dict(conn.execute("SELECT city_name, city_id FROM dim_city"))
            rows = to_fact_rows(df, city_ids)
            conn.executemany(FACT_UPSERT_SQL, rows)
    logger.info("Loaded %d fact rows into %s", len(rows), db_path)
    return len(rows)


def write_parquet(df: pd.DataFrame, processed_dir: Path) -> Path:
    """Write the full transformed frame to a run_date-partitioned Parquet file."""
    now = datetime.now(timezone.utc)
    folder = Path(processed_dir) / "weather_hourly" / f"run_date={now:%Y-%m-%d}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"part-{now:%Y%m%dT%H%M%S}.parquet"
    df.to_parquet(path, index=False)
    logger.info("Wrote %d rows to %s", len(df), path)
    return path