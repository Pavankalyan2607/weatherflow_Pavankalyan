"""Command line entry point: python -m weatherflow run"""
from __future__ import annotations

import argparse
import logging

from weatherflow.pipeline import run


def main() -> None:
    """Parse arguments and run the chosen command."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    parser = argparse.ArgumentParser(prog="weatherflow")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Run Extract, Transform and Load once")
    args = parser.parse_args()
    if args.command == "run":
        run()


if __name__ == "__main__":
    main()