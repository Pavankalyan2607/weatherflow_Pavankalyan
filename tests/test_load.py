import sqlite3
from contextlib import closing

import pytest

from weatherflow.config import load_config
from weatherflow.load import load
from weatherflow.lookups import load_wmo_codes
from weatherflow.transform import transform


@pytest.fixture
def df(london_payload):
    return transform([("London", london_payload)], load_wmo_codes(), "2026-11-19T00:00:00")


def count_rows(db_path, table):
    with closing(sqlite3.connect(db_path)) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_load_inserts_one_fact_row_per_hour(tmp_path, df):
    db = tmp_path / "test.db"

    load(df, db, load_config())

    assert count_rows(db, "fact_weather_hourly") == len(df)
    assert count_rows(db, "dim_city") == 5


def test_loading_same_data_twice_does_not_duplicate_rows(tmp_path, df):
    db = tmp_path / "test.db"
    cfg = load_config()

    load(df, db, cfg)
    first = count_rows(db, "fact_weather_hourly")
    load(df, db, cfg)
    second = count_rows(db, "fact_weather_hourly")

    assert first == second == len(df)


def test_failed_load_rolls_back_all_fact_rows(tmp_path, df):
    db = tmp_path / "test.db"
    bad_df = df.copy()
    bad_df.loc[3, "outdoor_work_risk"] = "extreme"  # violates the CHECK constraint

    with pytest.raises(sqlite3.IntegrityError):
        load(bad_df, db, load_config())

    assert count_rows(db, "fact_weather_hourly") == 0