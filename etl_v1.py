import sqlite3
from datetime import datetime, timezone

import pandas as pd
import requests

from extract import CITIES, fetch_city, save_raw  # reused from Task 1.3

DB_PATH = "weather.db"

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

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS weather_hourly (
    city              TEXT    NOT NULL,
    observed_at       TEXT    NOT NULL,
    temperature_c     REAL,
    feels_like_c      REAL,
    humidity_pct      INTEGER,
    precipitation_mm  REAL,
    wind_speed_kmh    REAL,
    weather_code      INTEGER,
    ingested_at_utc   TEXT    NOT NULL,
    PRIMARY KEY (city, observed_at)
);
"""

INSERT_SQL = """
INSERT OR REPLACE INTO weather_hourly
(city, observed_at, temperature_c, feels_like_c, humidity_pct,
 precipitation_mm, wind_speed_kmh, weather_code, ingested_at_utc)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def flatten(payload: dict, city_name: str) -> pd.DataFrame:
    # moved here from notebooks/01_explore.ipynb (Task 1.4)
    df = pd.DataFrame(payload["hourly"])
    df["city"] = city_name
    return df


def extract() -> list[tuple[str, dict]]:
    results = []
    for city in CITIES:
        try:
            payload = fetch_city(city)
            save_raw(city["name"], payload)
            results.append((city["name"], payload))
        except requests.RequestException as e:
            print(f"ERROR {city['name']}: {e}")
    return results


def transform(raw: list[tuple[str, dict]]) -> pd.DataFrame:
    ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    df = pd.concat([flatten(p, c) for c, p in raw], ignore_index=True)
    df["time"] = pd.to_datetime(df["time"])
    df = df.rename(columns=RENAME)
    df["ingested_at_utc"] = ingested_at
    df = df.drop_duplicates(subset=["city", "observed_at"], keep="last")
    df["observed_at"] = df["observed_at"].dt.strftime("%Y-%m-%dT%H:%M")
    return df[COLUMNS]


def load(df: pd.DataFrame, db_path: str = DB_PATH) -> int:
    rows = list(df.astype(object).where(df.notna(), None)
                  .itertuples(index=False, name=None))
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.executemany(INSERT_SQL, rows)
    return len(rows)


def main():
    raw = extract()
    if not raw:
        print("No data extracted, nothing to load")
        return
    df = transform(raw)
    rows = load(df)
    print(f"Loaded {rows} rows")


if __name__ == "__main__":
    main()