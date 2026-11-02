# feature_pipeline/orchestrator.py
"""
Feature Pipeline Orchestrator.

Runs all feature computers in dependency order:
  1. EloRatings        - depends only on Matches
  2. TeamFormStats     - depends only on Matches
  3. TeamSeasonLocationStats - depends only on Matches
  4. HeadToHeadStats   - depends only on Matches
  5. RefereeStats      - depends on Matches + MatchEvents

Usage:
    # Compute everything:
    python -m feature_pipeline.orchestrator

    # Incremental (one season):
    python -m feature_pipeline.orchestrator --season "2023/24"

    # Skip ELO (expensive, rerun separately):
    python -m feature_pipeline.orchestrator --skip elo
"""

import sys
import argparse
import logging
from datetime import datetime
from typing import Optional, List

from utils.db_connector import DatabaseConnector
from utils.logging_config import setup_logging
from feature_pipeline.computers import (
    EloComputer,
    FormComputer,
    H2HComputer,
    RefereeComputer,
    SeasonComputer,
)
from feature_pipeline.computers.base_computer import AbstractFeatureComputer, ComputerError

logger = logging.getLogger(__name__)


# Ordered list - ELO must run before anything that uses it downstream.
COMPUTERS: List[AbstractFeatureComputer] = [
    EloComputer(),
    FormComputer(),
    SeasonComputer(),
    H2HComputer(),
    RefereeComputer(),
]


def run_feature_pipeline(
    season_name: Optional[str] = None,
    skip: Optional[List[str]] = None,
) -> dict:
    """
    Execute all feature computers sequentially.

    Args:
        season_name: Restrict computation to this season (e.g. '2023/24').
                     None = all seasons.
        skip:        List of computer names to skip (e.g. ['elo']).

    Returns:
        Summary dict with per-computer row counts and errors.
    """
    skip_set = {s.lower() for s in (skip or [])}
    t_start = datetime.now()
    summary = {"success": True, "computers": {}, "duration_seconds": 0.0}

    if not DatabaseConnector.check_connection():
        logger.critical("Cannot connect to database. Aborting feature pipeline.")
        summary["success"] = False
        return summary

    for computer in COMPUTERS:
        cname = computer.name.lower()
        if any(s in cname for s in skip_set):
            logger.info("Skipping %s (in --skip list).", computer.name)
            summary["computers"][computer.name] = {"skipped": True}
            continue

        logger.info("=== Running %s ===", computer.name)
        t0 = datetime.now()
        try:
            with DatabaseConnector.session_scope() as session:
                rows = computer.compute(session, season_name=season_name)
            duration = (datetime.now() - t0).total_seconds()
            summary["computers"][computer.name] = {"rows": rows, "duration_s": duration}
            logger.info("%s done: %d rows in %.1fs.", computer.name, rows, duration)
        except ComputerError as exc:
            logger.error("%s failed: %s", computer.name, exc, exc_info=True)
            summary["computers"][computer.name] = {"error": str(exc)}
            summary["success"] = False
        except Exception as exc:
            logger.error("%s unexpected error: %s", computer.name, exc, exc_info=True)
            summary["computers"][computer.name] = {"error": str(exc)}
            summary["success"] = False

    summary["duration_seconds"] = (datetime.now() - t_start).total_seconds()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Feature Pipeline - compute all aggregated ML features from raw match data.",
        epilog='Example: python -m feature_pipeline.orchestrator --season "2023/24"',
    )
    parser.add_argument("--season", default=None, metavar="SEASON",
                        help='Limit to one season, e.g. "2023/24". Default: all seasons.')
    parser.add_argument("--skip", nargs="*", default=[],
                        help="Computer names to skip (case-insensitive substring match).")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    setup_logging(log_level=args.log_level)

    logger.info("=" * 60)
    logger.info("Feature Pipeline | Season: %s", args.season or "ALL")
    logger.info("=" * 60)

    result = run_feature_pipeline(season_name=args.season, skip=args.skip)

    logger.info("=" * 60)
    logger.info("Feature Pipeline complete in %.1fs | success=%s",
                result["duration_seconds"], result["success"])
    for name, stats in result["computers"].items():
        logger.info("  %-30s %s", name, stats)
    logger.info("=" * 60)

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())

