"""Command line entry point: python -m weatherflow run | backfill"""
from __future__ import annotations

import argparse
import logging
from datetime import date

from weatherflow.pipeline import backfill, run


def main() -> None:
    """Parse arguments and run the chosen command."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    parser = argparse.ArgumentParser(prog="weatherflow")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="Incremental run: fetch only what is new, then validate and load")

    bf = sub.add_parser("backfill", help="Load history from the archive API")
    group = bf.add_mutually_exclusive_group()
    group.add_argument("--days", type=int, help="Number of days, ending 5 days before today")
    group.add_argument("--start-date", type=date.fromisoformat, help="YYYY-MM-DD")
    bf.add_argument("--end-date", type=date.fromisoformat, help="YYYY-MM-DD")

    args = parser.parse_args()
    if args.command == "run":
        run()
    elif args.command == "backfill":
        backfill(args.days, args.start_date, args.end_date)


if __name__ == "__main__":
    main()