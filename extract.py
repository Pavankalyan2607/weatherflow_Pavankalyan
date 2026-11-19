import json
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY = ("temperature_2m,relative_humidity_2m,apparent_temperature,"
          "precipitation,wind_speed_10m,weather_code")
CITIES = [
    {"name": "London", "latitude": 51.5085, "longitude": -0.1257},
    {"name": "Manchester", "latitude": 53.48095, "longitude": -2.23743},
    {"name": "Birmingham", "latitude": 52.4814, "longitude": -1.8998},
    {"name": "Edinburgh", "latitude": 55.9521, "longitude": -3.1965},
    {"name": "Cardiff", "latitude": 51.48, "longitude": -3.18},
]

def fetch_city(city: dict) -> dict:
    params = {
        "latitude": city["latitude"],
        "longitude": city["longitude"],
        "hourly": HOURLY,
        "past_days": 1,
        "forecast_days": 1,
        "timezone": "Europe/London",
    }
    response = requests.get(BASE_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()

def save_raw(city_name: str, payload: dict) -> Path:
    now = datetime.now(timezone.utc)
    folder = Path("data/raw") / now.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{city_name.lower()}_{now.strftime('%Y%m%dT%H%M%S')}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path

if __name__ == "__main__":
    for city in CITIES:
        try:
            payload = fetch_city(city)
            path = save_raw(city["name"], payload)
            count = len(payload["hourly"]["time"])
            print(f"{city['name']}: {count} hourly records -> {path}")
        except requests.RequestException as e:
            print(f"ERROR {city['name']}: {e}")