import pytest
import requests

from weatherflow import extract as ex

API_CFG = {
    "forecast_url": "https://example.test/forecast",
    "hourly_variables": ["temperature_2m"],
    "timezone": "UTC",
    "timeout_seconds": 10,
    "max_retries": 3,
}
CITY = {"name": "London", "latitude": 51.5, "longitude": -0.1}


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)

    def json(self):
        return self._payload


def make_fake_get(responses):
    """Return a fake requests.get that yields the given responses/exceptions in order."""
    calls = {"n": 0}

    def fake_get(*args, **kwargs):
        item = responses[calls["n"]]
        calls["n"] += 1
        if isinstance(item, Exception):
            raise item
        return item

    return fake_get, calls


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("weatherflow.extract.time.sleep", lambda s: None)


def test_fetch_retries_on_server_error(monkeypatch):
    fake_get, calls = make_fake_get(
        [FakeResponse(503), FakeResponse(503), FakeResponse(200, {"ok": True})]
    )
    monkeypatch.setattr("weatherflow.extract.requests.get", fake_get)

    result = ex.fetch_city(CITY, API_CFG)

    assert calls["n"] == 3
    assert result == {"ok": True}


def test_fetch_does_not_retry_on_404(monkeypatch):
    fake_get, calls = make_fake_get([FakeResponse(404)])
    monkeypatch.setattr("weatherflow.extract.requests.get", fake_get)

    with pytest.raises(requests.HTTPError):
        ex.fetch_city(CITY, API_CFG)

    assert calls["n"] == 1


def test_fetch_gives_up_after_max_retries(monkeypatch):
    fake_get, calls = make_fake_get([FakeResponse(503)] * 4)
    monkeypatch.setattr("weatherflow.extract.requests.get", fake_get)

    with pytest.raises(requests.HTTPError):
        ex.fetch_city(CITY, API_CFG)

    assert calls["n"] == 4  # 1 first try + 3 retries


def test_fetch_retries_on_timeout(monkeypatch):
    fake_get, calls = make_fake_get(
        [requests.Timeout("slow"), FakeResponse(200, {"ok": True})]
    )
    monkeypatch.setattr("weatherflow.extract.requests.get", fake_get)

    result = ex.fetch_city(CITY, API_CFG)

    assert calls["n"] == 2
    assert result == {"ok": True}


@pytest.mark.parametrize(
    "status, expected",
    [(500, True), (503, True), (400, False), (404, False)],
)
def test_is_retryable_depends_on_status_code(status, expected):
    exc = requests.HTTPError("err", response=FakeResponse(status))
    assert ex._is_retryable(exc) is expected


def test_save_raw_writes_unchanged_payload_to_tmp_path(tmp_path, london_payload):
    path = ex.save_raw("London", london_payload, tmp_path)

    assert path.exists()
    assert path.parent.parent == tmp_path
    assert path.name.startswith("london_")
    import json
    assert json.loads(path.read_text(encoding="utf-8")) == london_payload


def test_extract_continues_when_one_city_fails(monkeypatch, tmp_path, london_payload):
    def fake_fetch(city, api_cfg):
        if city["name"] == "Broken":
            raise requests.ConnectionError("down")
        return london_payload

    monkeypatch.setattr("weatherflow.extract.fetch_city", fake_fetch)
    cfg = {
        "cities": [
            {"name": "London", "latitude": 51.5, "longitude": -0.1},
            {"name": "Broken", "latitude": 0, "longitude": 0},
        ],
        "api": API_CFG,
        "paths": {"raw_dir": tmp_path},
    }

    results = ex.extract(cfg)

    assert [name for name, _ in results] == ["London"]