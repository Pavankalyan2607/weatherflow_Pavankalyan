import copy

import pandas as pd
import pytest

from weatherflow.lookups import load_wmo_codes
from weatherflow.transform import _outdoor_work_risk, transform

INGESTED_AT = "2026-11-19T00:00:00"

EXPECTED_COLUMNS = {
    "city",
    "observed_at_utc",
    "observed_at_local",
    "temperature_c",
    "temperature_f",
    "feels_like_c",
    "humidity_pct",
    "precipitation_mm",
    "wind_speed_kmh",
    "wind_speed_ms",
    "beaufort_scale",
    "weather_code",
    "weather_description",
    "weather_category",
    "is_daylight",
    "outdoor_work_risk",
    "ingested_at_utc",
}


def run_transform(payload, city="London"):
    return transform([(city, payload)], load_wmo_codes(), INGESTED_AT)


def test_transform_returns_one_row_per_hour_with_expected_columns(london_payload):
    df = run_transform(london_payload)

    assert len(df) == 6
    assert EXPECTED_COLUMNS <= set(df.columns)


def test_temperature_fahrenheit_is_converted_from_celsius(london_payload):
    df = run_transform(london_payload)

    expected_f = df["temperature_c"] * 9 / 5 + 32
    assert df["temperature_f"].tolist() == pytest.approx(expected_f.tolist(), abs=0.01)


def test_wind_speed_ms_is_kmh_divided_by_3_6(london_payload):
    df = run_transform(london_payload)

    expected = df["wind_speed_kmh"] / 3.6
    assert df["wind_speed_ms"].tolist() == pytest.approx(expected.tolist(), abs=0.001)


def test_unknown_weather_code_becomes_unknown_category(london_payload):
    payload = copy.deepcopy(london_payload)
    payload["hourly"]["weather_code"][0] = 9999

    df = run_transform(payload)

    row = df[df["weather_code"] == 9999].iloc[0]
    assert row["weather_category"] == "unknown"


def test_known_weather_code_is_mapped_to_description(london_payload):
    payload = copy.deepcopy(london_payload)
    payload["hourly"]["weather_code"][0] = 51

    df = run_transform(payload)

    row = df[df["weather_code"] == 51].iloc[0]
    assert row["weather_description"] == "Light drizzle"
    assert row["weather_category"] == "drizzle"


def test_duplicate_hours_are_deduplicated(london_payload):
    df = transform(
        [("London", london_payload), ("London", london_payload)],
        load_wmo_codes(),
        INGESTED_AT,
    )

    assert len(df) == 6
    assert not df.duplicated(subset=["city", "observed_at_utc"]).any()


def test_ingested_at_is_stamped_on_every_row(london_payload):
    df = run_transform(london_payload)

    assert (df["ingested_at_utc"] == INGESTED_AT).all()


@pytest.mark.parametrize(
    "beaufort, rain_mm, category, temp_c, expected",
    [
        pytest.param(0, 0.0, "cloudy", 10.0, "low", id="calm_dry_mild_is_low"),
        pytest.param(4, 0.9, "cloudy", 10.0, "low", id="just_below_medium_limits_is_low"),
        pytest.param(5, 0.0, "cloudy", 10.0, "medium", id="beaufort_5_is_medium"),
        pytest.param(0, 1.0, "cloudy", 10.0, "medium", id="exactly_1mm_rain_is_medium"),
        pytest.param(0, 0.0, "cloudy", 0.0, "medium", id="exactly_0c_is_medium"),
        pytest.param(0, 0.0, "cloudy", 0.1, "low", id="just_above_0c_is_low"),
        pytest.param(6, 3.9, "cloudy", 10.0, "medium", id="just_below_high_limits_is_medium"),
        pytest.param(7, 0.0, "cloudy", 10.0, "high", id="beaufort_7_is_high"),
        pytest.param(0, 4.0, "cloudy", 10.0, "high", id="exactly_4mm_rain_is_high"),
        pytest.param(0, 0.0, "storm", 10.0, "high", id="storm_category_is_high"),
        pytest.param(0, 0.0, "snow", 10.0, "high", id="snow_category_is_high"),
        pytest.param(7, 5.0, "storm", -2.0, "high", id="high_wins_over_medium"),
    ],
)
def test_outdoor_work_risk_rules_and_boundaries(beaufort, rain_mm, category, temp_c, expected):
    df = pd.DataFrame(
        [
            {
                "beaufort_scale": beaufort,
                "precipitation_mm": rain_mm,
                "weather_category": category,
                "temperature_c": temp_c,
            }
        ]
    )

    risk = _outdoor_work_risk(df)

    assert risk.iloc[0] == expected