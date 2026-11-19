"""Load and validate config.yaml."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# src/weatherflow/config.py -> project root
CONFIG_FILE = Path(__file__).resolve().parents[2] / "config.yaml"

REQUIRED_KEYS = {
    "api": ["forecast_url", "archive_url", "timeout_seconds", "max_retries",
            "hourly_variables", "timezone"],
    "paths": ["raw_dir", "processed_dir", "quarantine_dir", "database"],
}


def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    """Load config.yaml, check required keys and make all paths absolute."""
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    for section, keys in REQUIRED_KEYS.items():
        if section not in cfg:
            raise ValueError(f"config.yaml is missing the '{section}' section")
        for key in keys:
            if key not in cfg[section]:
                raise ValueError(f"config.yaml is missing '{section}.{key}'")
    if not cfg.get("cities"):
        raise ValueError("config.yaml is missing the 'cities' list")

    root = path.parent
    cfg["paths"] = {k: (root / v).resolve() for k, v in cfg["paths"].items()}
    logger.info("Loaded config from %s", path)
    return cfg