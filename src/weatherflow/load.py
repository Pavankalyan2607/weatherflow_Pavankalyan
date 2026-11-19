"""Load step: write rows into SQLite (idempotent)."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"

INSERT_SQL = """
INSERT OR REPLACE INTO weather_hourly
(city, observed_at, temperature_c, feels_like_c, humidity_pct,
 precipitation_mm, wind_speed_kmh, weather_code, ingested_at_utc)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def load(df: pd.DataFrame, db_path: Path) -> int:
    """Upsert rows into weather_hourly. Returns the number of rows written."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(df.astype(object).where(df.notna(), None)
                  .itertuples(index=False, name=None))
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        conn.executemany(INSERT_SQL, rows)
    logger.info("Loaded %d rows into %s", len(rows), db_path)
    return len(rows)