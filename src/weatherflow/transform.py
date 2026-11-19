"""Transform step: small pure functions that turn API payloads into a tidy table.

Nothing here reads files, calls APIs or touches the database.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

LOCAL_TZ = "Europe/London"

RENAME = {
    "time": "observed_at_utc",
    "temperature_2m": "temperature_c",
    "apparent_temperature": "feels_like_c",
    "relative_humidity_2m": "humidity_pct",
    "precipitation": "precipitation_mm",
    "wind_speed_10m": "wind_speed_kmh",
    "is_day": "is_daylight",
}

# Beaufort scale lower bounds in m/s: bands 0..12
BEAUFORT_BINS = [float("-inf"), 0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9,
                 17.2, 20.8, 24.5, 28.5, 32.7, float("inf")]

COLUMNS = [
    "city", "observed_at_utc", "observed_at_local",
    "temperature_c", "temperature_f", "feels_like_c", "humidity_pct",
    "precipitation_mm", "wind_speed_kmh", "wind_speed_ms", "beaufort_scale",
    "weather_code", "weather_description", "weather_category",
    "is_daylight", "outdoor_work_risk", "ingested_at_utc",
]


def flatten_payload(payload: dict[str, Any], city: str) -> pd.DataFrame:
    """Turn one API payload into a DataFrame with one row per hour."""
    df = pd.DataFrame(payload["hourly"])
    df["city"] = city
    return df


def standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns, parse time as UTC and derive London local time."""
    out = df.rename(columns=RENAME).copy()
    out["observed_at_utc"] = pd.to_datetime(out["observed_at_utc"], utc=True)
    out["observed_at_local"] = out["observed_at_utc"].dt.tz_convert(LOCAL_TZ)
    out["is_daylight"] = out["is_daylight"].eq(1)
    return out


def add_weather_description(df: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    """Join WMO description and category on weather_code. Unknown codes become 'unknown'."""
    out = df.merge(lookup, on="weather_code", how="left")
    out["weather_description"] = out["weather_description"].fillna("unknown")
    out["weather_category"] = out["weather_category"].fillna("unknown")
    return out


def _outdoor_work_risk(df: pd.DataFrame) -> pd.Series:
    """Classify outdoor work risk as high, medium or low using the business rules."""
    beaufort = df["beaufort_scale"].fillna(0)
    rain = df["precipitation_mm"].fillna(0)
    high = (beaufort >= 7) | df["weather_category"].isin(["storm", "snow"]) | (rain >= 4)
    medium = (beaufort >= 5) | (rain >= 1) | (df["temperature_c"] <= 0)
    risk = np.select([high.to_numpy(), medium.to_numpy()], ["high", "medium"], default="low")
    return pd.Series(risk, index=df.index)


def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add temperature_f, wind_speed_ms, beaufort_scale and outdoor_work_risk."""
    out = df.copy()
    out["temperature_f"] = out["temperature_c"] * 9 / 5 + 32
    out["wind_speed_ms"] = out["wind_speed_kmh"] / 3.6
    out["beaufort_scale"] = pd.cut(
        out["wind_speed_ms"], bins=BEAUFORT_BINS, labels=False, right=False
    ).astype("Int64")
    out["outdoor_work_risk"] = _outdoor_work_risk(out)
    return out


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the latest ingested row for each (city, observed_at_utc)."""
    before = len(df)
    out = (df.sort_values("ingested_at_utc")
             .drop_duplicates(subset=["city", "observed_at_utc"], keep="last")
             .reset_index(drop=True))
    if len(out) < before:
        logger.warning("Dropped %d duplicate rows", before - len(out))
    return out


def transform(raw: list[tuple[str, dict[str, Any]]], wmo_lookup: pd.DataFrame,
              ingested_at: str) -> pd.DataFrame:
    """Run all transformations in order and return the final table."""
    df = pd.concat([flatten_payload(p, c) for c, p in raw], ignore_index=True)
    df = standardise_columns(df)
    df["ingested_at_utc"] = ingested_at
    df = add_weather_description(df, wmo_lookup)
    df = add_derived_metrics(df)
    df = deduplicate(df)
    logger.info("Transformed %d rows", len(df))
    return (df[COLUMNS].sort_values(["city", "observed_at_utc"])
              .reset_index(drop=True))