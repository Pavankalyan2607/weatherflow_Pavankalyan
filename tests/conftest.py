import json
from pathlib import Path

import pytest


@pytest.fixture
def london_payload():
    path = Path(__file__).parent / "fixtures" / "open_meteo_london.json"
    return json.loads(path.read_text(encoding="utf-8"))