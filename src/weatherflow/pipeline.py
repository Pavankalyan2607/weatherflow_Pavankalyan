"""Wire Extract, Transform and Load together."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from weatherflow.config import load_config
from weatherflow.extract import extract
from weatherflow.load import load, write_parquet
from weatherflow.lookups import load_wmo_codes
from weatherflow.transform import transform

logger = logging.getLogger(__name__)


def run() -> int:
    """Run the full pipeline. Returns the number of rows loaded."""
    start = time.perf_counter()
    cfg = load_config()
    raw = extract(cfg)
    if not raw:
        logger.error("No data extracted, nothing to load")
        return 0
    ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    df = transform(raw, load_wmo_codes(), ingested_at)
    write_parquet(df, Path(cfg["paths"]["processed_dir"]))
    rows = load(df, Path(cfg["paths"]["database"]), cfg)
    logger.info("Pipeline finished: %d rows in %.1fs", rows, time.perf_counter() - start)
    return rows