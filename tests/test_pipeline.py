import copy
import sqlite3
from contextlib import closing

import pytest

from weatherflow import pipeline
from weatherflow.config import load_config
from weatherflow.load import SOURCE_ARCHIVE, SOURCE_FORECAST


@pytest.fixture
def cfg(tmp_path):
    cfg = copy.deepcopy(load_config())
    cfg["cities"] = [c for c in cfg["cities"] if c["name"] == "London"]
    cfg["data_quality"]["min_hours_per_city"] = 6  # the fixture holds 6 hours
    cfg["data_quality"]["report_dir"] = str(tmp_path / "dq_reports")
    cfg["paths"] = {
        "raw_dir": tmp_path / "raw",
        "processed_dir": tmp_path / "processed",
        "quarantine_dir": tmp_path / "quarantine",
        "database": tmp_path / "weather.db",
    }
    return cfg


def rows_by_source(cfg):
    with closing(sqlite3.connect(cfg["paths"]["database"])) as conn:
        return dict(
            conn.execute("SELECT source, COUNT(*) FROM fact_weather_hourly GROUP BY source")
        )


def test_backfill_loads_rows_with_the_archive_source(monkeypatch, cfg, london_payload):
    monkeypatch.setattr(pipeline, "load_config", lambda: cfg)
    monkeypatch.setattr(
        pipeline, "extract_backfill", lambda c, start, end: [("London", london_payload)]
    )

    rows = pipeline.backfill(days=1)

    assert rows == 6
    assert rows_by_source(cfg) == {SOURCE_ARCHIVE: 6}


def test_running_backfill_twice_does_not_change_row_counts(monkeypatch, cfg, london_payload):
    monkeypatch.setattr(pipeline, "load_config", lambda: cfg)
    monkeypatch.setattr(
        pipeline, "extract_backfill", lambda c, start, end: [("London", london_payload)]
    )

    pipeline.backfill(days=1)
    pipeline.backfill(days=1)

    assert rows_by_source(cfg) == {SOURCE_ARCHIVE: 6}


def test_run_falls_back_first_then_requests_only_a_recent_window(
    monkeypatch, cfg, london_payload
):
    seen = []

    def fake_extract(c, windows=None):
        seen.append(windows)
        return [("London", london_payload)]

    monkeypatch.setattr(pipeline, "load_config", lambda: cfg)
    monkeypatch.setattr(pipeline, "extract", fake_extract)

    pipeline.run()
    pipeline.run()

    assert seen[0] == {"London": None}  # nothing loaded yet: past_days=1 fallback
    start, end = seen[1]["London"]  # second run: only recent dates are requested
    assert start <= end
    assert rows_by_source(cfg) == {SOURCE_FORECAST: 6}