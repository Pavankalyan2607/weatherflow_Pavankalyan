"""Wire Extract, Transform and Load together."""
from __future__ import annotations

import logging
import time

from weatherflow.config import load_config
from weatherflow.extract import extract
from weatherflow.load import load
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
    df = transform(raw)
    rows = load(df, cfg["paths"]["database"])
    logger.info("Pipeline finished: %d rows in %.1fs", rows, time.perf_counter() - start)
    return rows