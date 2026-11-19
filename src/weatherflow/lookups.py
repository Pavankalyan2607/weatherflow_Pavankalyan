"""Load reference lookup tables (WMO weather codes)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

WMO_FILE = Path(__file__).resolve().parent / "reference" / "wmo_codes.csv"


def load_wmo_codes(path: Path = WMO_FILE) -> pd.DataFrame:
    """Read the WMO weather code lookup as (weather_code, weather_description, weather_category)."""
    df = pd.read_csv(path)
    return df.rename(columns={
        "code": "weather_code",
        "description": "weather_description",
        "category": "weather_category",
    })