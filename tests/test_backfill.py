import logging
from datetime import date

import pytest
import requests

from weatherflow import extract as ex
from weatherflow.extract import date_chunks
from weatherflow.pipeline import resolve_backfill_range

CFG = {"backfill": {"default_days": 30, "lag_days": 5, "chunk_days": 7, "sleep_seconds": 1}}
TODAY = date(2026, 11, 19)


def test_chunks_cover_every_day_exactly_once_in_seven_day_pieces():
    chunks = list(date_chunks(date(2026, 10, 16), date(2026, 11, 14), 7))

    assert len(chunks) == 5
    assert chunks[0] == (date(2026, 10, 16), date(2026, 10, 22))
    assert chunks[-1] == (date(2026, 11, 13), date(2026, 11, 14))  # shorter last chunk
    assert sum((end - start).days + 1 for start, end in chunks) == 30


def test_single_day_range_is_one_chunk():
    assert list(date_chunks(date(2026, 11, 1), date(2026, 11, 1), 7)) == [
        (date(2026, 11, 1), date(2026, 11, 1))
    ]


def test_default_backfill_is_30_days_ending_five_days_before_today():
    assert resolve_backfill_range(CFG, None, None, None, TODAY) == (
        date(2026, 10, 16),
        date(2026, 11, 14),
    )


def test_days_option_sets_the_length_of_the_window():
    assert resolve_backfill_range(CFG, 10, None, None, TODAY) == (
        date(2026, 11, 5),
        date(2026, 11, 14),
    )


def test_explicit_start_and_end_dates_are_used_as_given():
    start, end = date(2026, 1, 1), date(2026, 1, 31)

    assert resolve_backfill_range(CFG, None, start, end, TODAY) == (start, end)


def test_start_date_after_end_date_is_rejected():
    with pytest.raises(ValueError):
        resolve_backfill_range(CFG, None, date(2026, 11, 10), date(2026, 11, 1), TODAY)


def test_end_date_newer_than_the_archive_lag_logs_a_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="weatherflow.pipeline"):
        resolve_backfill_range(CFG, None, None, TODAY, TODAY)

    assert "archive lags" in caplog.text


def _two_city_cfg(tmp_path):
    return {
        "cities": [
            {"name": "London", "latitude": 51.5, "longitude": -0.1},
            {"name": "Cardiff", "latitude": 51.48, "longitude": -3.18},
        ],
        "api": {},
        "paths": {"raw_dir": tmp_path},
        "backfill": {"chunk_days": 7, "sleep_seconds": 1},
    }


def test_backfill_requests_one_chunk_per_week_per_city_and_pauses_between(
    monkeypatch, tmp_path, london_payload
):
    made, sleeps = [], []

    def fake_fetch_range(city, api_cfg, start, end, url_key="forecast_url"):
        made.append((city["name"], start, end, url_key))
        return london_payload

    monkeypatch.setattr("weatherflow.extract.fetch_range", fake_fetch_range)
    monkeypatch.setattr("weatherflow.extract.time.sleep", sleeps.append)

    results = ex.extract_backfill(_two_city_cfg(tmp_path), date(2026, 11, 1), date(2026, 11, 14))

    assert len(made) == 4  # 2 cities x 2 weeks
    assert all(call[3] == "archive_url" for call in made)
    assert len(results) == 4
    assert sleeps == [1, 1, 1]  # between requests, not before the first
    assert len(list(tmp_path.rglob("*.json"))) == 4  # every chunk lands as raw JSON


def test_backfill_skips_a_failed_chunk_and_keeps_the_rest(monkeypatch, tmp_path, london_payload):
    def fake_fetch_range(city, api_cfg, start, end, url_key="forecast_url"):
        if start == date(2026, 11, 8):
            raise requests.ConnectionError("down")
        return london_payload

    monkeypatch.setattr("weatherflow.extract.fetch_range", fake_fetch_range)
    monkeypatch.setattr("weatherflow.extract.time.sleep", lambda s: None)
    cfg = _two_city_cfg(tmp_path)
    cfg["cities"] = cfg["cities"][:1]

    results = ex.extract_backfill(cfg, date(2026, 11, 1), date(2026, 11, 14))

    assert len(results) == 1  # the first week survived, the failed week was skipped


def test_extract_uses_the_date_window_when_given_and_falls_back_otherwise(
    monkeypatch, tmp_path, london_payload
):
    calls = []

    def fake_fetch_range(city, api_cfg, start, end, url_key="forecast_url"):
        calls.append(("range", city["name"], start, end))
        return london_payload

    def fake_fetch_city(city, api_cfg):
        calls.append(("fallback", city["name"]))
        return london_payload

    monkeypatch.setattr("weatherflow.extract.fetch_range", fake_fetch_range)
    monkeypatch.setattr("weatherflow.extract.fetch_city", fake_fetch_city)
    cfg = _two_city_cfg(tmp_path)
    windows = {"London": (date(2026, 11, 18), date(2026, 11, 19)), "Cardiff": None}

    ex.extract(cfg, windows)

    assert calls == [
        ("range", "London", date(2026, 11, 18), date(2026, 11, 19)),
        ("fallback", "Cardiff"),
    ]