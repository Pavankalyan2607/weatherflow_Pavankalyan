import copy

import pandas as pd
import pytest

from weatherflow.config import load_config
from weatherflow.lookups import load_wmo_codes
from weatherflow.transform import transform
from weatherflow.validate import DataQualityError, raise_for_blocking, validate


@pytest.fixture
def cfg():
    cfg = copy.deepcopy(load_config())
    cfg["data_quality"]["min_hours_per_city"] = 6  # fixture has only 6 hours
    cfg["cities"] = [c for c in cfg["cities"] if c["name"] == "London"]
    return cfg


@pytest.fixture
def clean_df(london_payload):
    return transform([("London", london_payload)], load_wmo_codes(), "2026-11-19T00:00:00")


def test_clean_dataframe_passes_all_blocking_checks(clean_df, cfg):
    good, bad, results = validate(clean_df, cfg)

    blocking = [r for r in results if r.severity in ("fail", "quarantine")]
    assert all(r.passed for r in blocking)
    assert len(good) == len(clean_df)
    assert len(bad) == 0
    raise_for_blocking(results)  # must not raise


def test_temperature_above_range_is_quarantined_with_reason(clean_df, cfg):
    df = clean_df.copy()
    df.loc[0, "temperature_c"] = 99.0

    good, bad, _ = validate(df, cfg)

    assert len(bad) == 1
    assert len(good) == len(df) - 1
    assert "temperature_in_range" in bad.iloc[0]["dq_failure_reason"]


def test_humidity_above_100_is_quarantined(clean_df, cfg):
    df = clean_df.copy()
    df.loc[0, "humidity_pct"] = 150

    _, bad, _ = validate(df, cfg)

    assert len(bad) == 1
    assert "humidity_in_range" in bad.iloc[0]["dq_failure_reason"]


def test_negative_precipitation_is_quarantined(clean_df, cfg):
    df = clean_df.copy()
    df.loc[0, "precipitation_mm"] = -1.0

    _, bad, _ = validate(df, cfg)

    assert len(bad) == 1
    assert "non_negative_precip_wind" in bad.iloc[0]["dq_failure_reason"]


def test_missing_temperature_is_quarantined(clean_df, cfg):
    df = clean_df.copy()
    df.loc[0, "temperature_c"] = None

    _, bad, _ = validate(df, cfg)

    assert len(bad) == 1
    assert "required_not_null" in bad.iloc[0]["dq_failure_reason"]


def test_duplicate_key_raises_data_quality_error(clean_df, cfg):
    df = pd.concat([clean_df, clean_df.iloc[[0]]], ignore_index=True)

    _, _, results = validate(df, cfg)

    with pytest.raises(DataQualityError):
        raise_for_blocking(results)


def test_unknown_weather_category_only_warns_and_keeps_row(clean_df, cfg):
    df = clean_df.copy()
    df.loc[0, "weather_category"] = "unknown"

    good, bad, results = validate(df, cfg)

    assert len(bad) == 0
    assert len(good) == len(df)
    raise_for_blocking(results)  # warn-level must not stop the run