"""Extract step: call Open-Meteo and save raw JSON."""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import requests

logger = logging.getLogger(__name__)


def _is_retryable(exc: requests.RequestException) -> bool:
    """Retry timeouts, connection errors and 5xx. Never retry 4xx."""
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    return False


def _base_params(city: dict[str, Any], api_cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "latitude": city["latitude"],
        "longitude": city["longitude"],
        "hourly": ",".join(api_cfg["hourly_variables"]),
        "timezone": api_cfg["timezone"],
    }


def _get_json(
    url: str, params: dict[str, Any], api_cfg: dict[str, Any], label: str
) -> dict[str, Any]:
    """GET with retries and exponential backoff."""
    attempts = api_cfg["max_retries"] + 1
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, params=params, timeout=api_cfg["timeout_seconds"])
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            if not _is_retryable(exc) or attempt == attempts:
                raise
            wait = 2 ** (attempt - 1)  # 1s, 2s, 4s
            logger.warning("%s: attempt %d/%d failed (%s). Retrying in %ds",
                           label, attempt, attempts, exc, wait)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def fetch_city(city: dict[str, Any], api_cfg: dict[str, Any]) -> dict[str, Any]:
    """Fetch yesterday and today (the fallback when nothing is loaded yet)."""
    params = {**_base_params(city, api_cfg), "past_days": 1, "forecast_days": 1}
    return _get_json(api_cfg["forecast_url"], params, api_cfg, city["name"])


def fetch_range(
    city: dict[str, Any],
    api_cfg: dict[str, Any],
    start_date: date,
    end_date: date,
    url_key: str = "forecast_url",
) -> dict[str, Any]:
    """Fetch a date range. url_key picks the forecast or the archive endpoint."""
    params = {
        **_base_params(city, api_cfg),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    logger.info("%s: requesting %s to %s (%s)", city["name"], start_date, end_date, url_key)
    return _get_json(api_cfg[url_key], params, api_cfg, city["name"])


def save_raw(city_name: str, payload: dict[str, Any], raw_dir: Path, suffix: str = "") -> Path:
    """Save the unchanged API response to raw_dir/<date>/<city>_<timestamp><suffix>.json."""
    now = datetime.now(timezone.utc)
    folder = raw_dir / now.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{city_name.lower()}_{now.strftime('%Y%m%dT%H%M%S')}{suffix}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def date_chunks(start: date, end: date, chunk_days: int) -> Iterator[tuple[date, date]]:
    """Split start..end (inclusive) into consecutive chunks of at most chunk_days days."""
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=chunk_days - 1), end)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def extract(
    cfg: dict[str, Any],
    windows: dict[str, tuple[date, date] | None] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Extract all configured cities. One failing city does not stop the others.

    windows maps a city name to the (start, end) dates to request. A city with no
    window falls back to yesterday + today.
    """
    windows = windows or {}
    results = []
    for city in cfg["cities"]:
        try:
            window = windows.get(city["name"])
            if window is None:
                payload = fetch_city(city, cfg["api"])
            else:
                payload = fetch_range(city, cfg["api"], window[0], window[1])
            path = save_raw(city["name"], payload, cfg["paths"]["raw_dir"])
            logger.info("%s: %d hourly records -> %s", city["name"],
                        len(payload["hourly"]["time"]), path)
            results.append((city["name"], payload))
        except requests.RequestException as exc:
            logger.error("%s: failed (%s)", city["name"], exc)
    return results


def extract_backfill(
    cfg: dict[str, Any], start: date, end: date
) -> list[tuple[str, dict[str, Any]]]:
    """Fetch history from the archive API in chunks per city, landing each chunk raw."""
    chunk_days = cfg["backfill"]["chunk_days"]
    pause = cfg["backfill"]["sleep_seconds"]
    results = []
    first = True
    for city in cfg["cities"]:
        for chunk_start, chunk_end in date_chunks(start, end, chunk_days):
            if not first:
                time.sleep(pause)  # be polite to the free API
            first = False
            try:
                payload = fetch_range(
                    city, cfg["api"], chunk_start, chunk_end, url_key="archive_url"
                )
            except requests.RequestException as exc:
                logger.error("%s %s to %s: failed (%s)", city["name"], chunk_start, chunk_end, exc)
                continue
            suffix = f"_{chunk_start:%Y%m%d}_{chunk_end:%Y%m%d}"
            path = save_raw(city["name"], payload, cfg["paths"]["raw_dir"], suffix)
            logger.info("%s: %d hourly records -> %s", city["name"],
                        len(payload["hourly"]["time"]), path)
            results.append((city["name"], payload))
    return results