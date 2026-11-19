"""Transform step: flatten, clean and standardise API payloads."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

RENAME = {
    "time": "observed_at",
    "temperature_2m": "temperature_c",
    "apparent_temperature": "feels_like_c",
    "relative_humidity_2m": "humidity_pct",
    "precipitation": "precipitation_mm",
    "wind_speed_10m": "wind_speed_kmh",
}
COLUMNS = ["city", "observed_at", "temperature_c", "feels_like_c",
           "humidity_pct", "precipitation_mm", "wind_speed_kmh",
           "weather_code", "ingested_at_utc"]


def flatten(payload: dict[str, Any], city_name: str) -> pd.DataFrame:
    """Turn one API payload into a DataFrame with one row per hour."""
    df = pd.DataFrame(payload["hourly"])
    df["city"] = city_name
    return df


def transform(raw: list[tuple[str, dict[str, Any]]]) -> pd.DataFrame:
    """Flatten, rename, convert types, add metadata and de-duplicate."""
    ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    df = pd.concat([flatten(p, c) for c, p in raw], ignore_index=True)
    df["time"] = pd.to_datetime(df["time"])
    df = df.rename(columns=RENAME)
    df["ingested_at_utc"] = ingested_at
    before = len(df)
    df = df.drop_duplicates(subset=["city", "observed_at"], keep="last")
    if len(df) < before:
        logger.warning("Dropped %d duplicate rows", before - len(df))
    df["observed_at"] = df["observed_at"].dt.strftime("%Y-%m-%dT%H:%M")
    logger.info("Transformed %d rows", len(df))
    return df[COLUMNS]