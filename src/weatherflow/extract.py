"""Extract step: call Open-Meteo and save raw JSON."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _is_retryable(exc: requests.RequestException) -> bool:
    """Retry timeouts, connection errors and 5xx. Never retry 4xx."""
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    return False


def fetch_city(city: dict[str, Any], api_cfg: dict[str, Any]) -> dict[str, Any]:
    """Fetch the forecast for one city, with retries and exponential backoff."""
    params = {
        "latitude": city["latitude"],
        "longitude": city["longitude"],
        "hourly": ",".join(api_cfg["hourly_variables"]),
        "past_days": 1,
        "forecast_days": 1,
        "timezone": api_cfg["timezone"],
    }
    attempts = api_cfg["max_retries"] + 1
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(api_cfg["forecast_url"], params=params,
                                    timeout=api_cfg["timeout_seconds"])
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            if not _is_retryable(exc) or attempt == attempts:
                raise
            wait = 2 ** (attempt - 1)  # 1s, 2s, 4s
            logger.warning("%s: attempt %d/%d failed (%s). Retrying in %ds",
                           city["name"], attempt, attempts, exc, wait)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def save_raw(city_name: str, payload: dict[str, Any], raw_dir: Path) -> Path:
    """Save the unchanged API response to raw_dir/<date>/<city>_<timestamp>.json."""
    now = datetime.now(timezone.utc)
    folder = raw_dir / now.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{city_name.lower()}_{now.strftime('%Y%m%dT%H%M%S')}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def extract(cfg: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Extract all configured cities. One failing city does not stop the others."""
    results = []
    for city in cfg["cities"]:
        try:
            payload = fetch_city(city, cfg["api"])
            path = save_raw(city["name"], payload, cfg["paths"]["raw_dir"])
            logger.info("%s: %d hourly records -> %s", city["name"],
                        len(payload["hourly"]["time"]), path)
            results.append((city["name"], payload))
        except requests.RequestException as exc:
            logger.error("%s: failed (%s)", city["name"], exc)
    return results