"""Load step: write rows into SQLite (idempotent) and Parquet."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"

DB_COLUMNS = [
    "city", "observed_at", "temperature_c", "feels_like_c", "humidity_pct",
    "precipitation_mm", "wind_speed_kmh", "weather_code", "ingested_at_utc",
]

INSERT_SQL = """
INSERT OR REPLACE INTO weather_hourly
(city, observed_at, temperature_c, feels_like_c, humidity_pct,
 precipitation_mm, wind_speed_kmh, weather_code, ingested_at_utc)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def to_db_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Shape the transformed frame for the v1 weather_hourly table."""
    out = df.copy()
    out["observed_at"] = out["observed_at_utc"].dt.strftime("%Y-%m-%dT%H:%M")
    return out[DB_COLUMNS]


def load(df: pd.DataFrame, db_path: Path) -> int:
    """Upsert rows into weather_hourly. Returns the number of rows written."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_df = to_db_frame(df)
    rows = list(db_df.astype(object).where(db_df.notna(), None)
                .itertuples(index=False, name=None))
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        conn.executemany(INSERT_SQL, rows)
    logger.info("Loaded %d rows into %s", len(rows), db_path)
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