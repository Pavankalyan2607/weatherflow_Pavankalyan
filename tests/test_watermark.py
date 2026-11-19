import logging
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from weatherflow.config import load_config
from weatherflow.load import SOURCE_ARCHIVE, SOURCE_FORECAST, load
from weatherflow.lookups import load_wmo_codes
from weatherflow.transform import transform
from weatherflow.watermark import (
    MAX_FORECAST_LOOKBACK_DAYS,
    compute_window,
    get_high_water_mark,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 19, 11, 30, tzinfo=UTC)


@pytest.fixture
def df(london_payload):
    return transform([("London", london_payload)], load_wmo_codes(), "2026-11-19T00:00:00")


@pytest.fixture
def hours(df):
    """The six distinct hours of the fixture, oldest first, as UTC datetimes."""
    ts = pd.to_datetime(df["observed_at_utc"], utc=True).drop_duplicates().sort_values()
    return [t.to_pydatetime() for t in ts]


def count_rows(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        return conn.execute("SELECT COUNT(*) FROM fact_weather_hourly").fetchone()[0]


# --- get_high_water_mark ---------------------------------------------------

def test_mark_is_latest_hour_that_has_already_happened(tmp_path, df, hours):
    db = tmp_path / "t.db"
    load(df, db, load_config(), source=SOURCE_FORECAST)
    now = hours[3] + timedelta(minutes=30)

    mark = get_high_water_mark(db, "London", SOURCE_FORECAST, now)

    assert mark == hours[3]  # hours 4 and 5 are still forecasts at this moment


def test_mark_is_none_when_all_loaded_hours_are_in_the_future(tmp_path, df, hours):
    db = tmp_path / "t.db"
    load(df, db, load_config(), source=SOURCE_FORECAST)

    mark = get_high_water_mark(db, "London", SOURCE_FORECAST, hours[0] - timedelta(hours=1))

    assert mark is None


def test_mark_is_tracked_per_source(tmp_path, df, hours):
    db = tmp_path / "t.db"
    load(df, db, load_config(), source=SOURCE_FORECAST)

    mark = get_high_water_mark(db, "London", SOURCE_ARCHIVE, hours[-1] + timedelta(hours=1))

    assert mark is None


def test_mark_is_tracked_per_city(tmp_path, df, hours):
    db = tmp_path / "t.db"
    load(df, db, load_config(), source=SOURCE_FORECAST)

    mark = get_high_water_mark(db, "Cardiff", SOURCE_FORECAST, hours[-1] + timedelta(hours=1))

    assert mark is None


def test_mark_is_none_when_database_does_not_exist(tmp_path):
    assert get_high_water_mark(tmp_path / "missing.db", "London", SOURCE_FORECAST, NOW) is None


def test_mark_is_none_when_tables_do_not_exist_yet(tmp_path):
    db = tmp_path / "empty.db"
    sqlite3.connect(db).close()

    assert get_high_water_mark(db, "London", SOURCE_FORECAST, NOW) is None


# --- compute_window --------------------------------------------------------

def test_window_is_none_without_a_mark():
    assert compute_window(None, NOW, 2) is None


def test_window_starts_from_the_mark_day():
    mark = datetime(2026, 11, 19, 10, 0, tzinfo=UTC)

    assert compute_window(mark, NOW, 2) == (date(2026, 11, 19), date(2026, 11, 19))


def test_overlap_can_reach_back_into_the_previous_day():
    mark = datetime(2026, 11, 19, 1, 0, tzinfo=UTC)  # 01:00 - 2h = 23:00 yesterday

    assert compute_window(mark, NOW, 2) == (date(2026, 11, 18), date(2026, 11, 19))


def test_window_never_reaches_further_back_than_the_forecast_api_allows():
    mark = NOW - timedelta(days=200)

    start, end = compute_window(mark, NOW, 2)

    assert start == (NOW - timedelta(days=MAX_FORECAST_LOOKBACK_DAYS)).date()
    assert end == NOW.date()


# --- load: new vs updated and sources --------------------------------------

def test_same_hour_from_two_sources_is_stored_separately(tmp_path, df):
    db = tmp_path / "t.db"

    load(df, db, load_config(), source=SOURCE_FORECAST)
    load(df, db, load_config(), source=SOURCE_ARCHIVE)

    assert count_rows(db) == 2 * len(df)


def test_second_load_reports_rows_as_updated_not_new(tmp_path, df, caplog):
    db = tmp_path / "t.db"

    with caplog.at_level(logging.INFO, logger="weatherflow.load"):
        load(df, db, load_config())
        load(df, db, load_config())

    assert f"{len(df)} new, 0 updated" in caplog.text
    assert f"0 new, {len(df)} updated" in caplog.text