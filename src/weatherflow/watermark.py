"""High-water mark logic for incremental loads."""
from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

TS_FORMAT = "%Y-%m-%dT%H:%M"
MAX_FORECAST_LOOKBACK_DAYS = 90  # the forecast API only serves about 92 past days

MARK_SQL = """
SELECT MAX(f.observed_at_utc)
FROM fact_weather_hourly AS f
JOIN dim_city AS c ON c.city_id = f.city_id
WHERE c.city_name = ? AND f.source = ? AND f.observed_at_utc <= ?
"""


def get_high_water_mark(
    db_path: Path, city_name: str, source: str, now_utc: datetime
) -> datetime | None:
    """Latest loaded hour that has already happened, or None if nothing is loaded.

    Hours after now_utc are forecasts, so they are ignored. Otherwise the mark
    would sit in the future and the next run would skip every hour in between.
    """
    if not Path(db_path).exists():
        return None
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            row = conn.execute(
                MARK_SQL, (city_name, source, now_utc.strftime(TS_FORMAT))
            ).fetchone()
    except sqlite3.OperationalError:  # tables not created yet
        return None
    if row is None or row[0] is None:
        return None
    return datetime.strptime(row[0], TS_FORMAT).replace(tzinfo=timezone.utc)


def compute_window(
    mark: datetime | None, now_utc: datetime, overlap_hours: int
) -> tuple[date, date] | None:
    """Dates to request: from (mark - overlap) to the end of today's forecast window.

    Returns None when there is no watermark yet. The caller then falls back to
    past_days=1.
    """
    if mark is None:
        return None
    start = (mark - timedelta(hours=overlap_hours)).date()
    earliest = (now_utc - timedelta(days=MAX_FORECAST_LOOKBACK_DAYS)).date()
    return max(start, earliest), now_utc.date()