# elt_pipeline/orchestrator.py
"""
Provider-agnostic ELT Orchestrator.

Design:
  - Depends ONLY on AbstractDataProvider interface - not SofaScore
  - Provider is injected at construction time (Dependency Injection)
  - Switching providers = change 1 env var + restart

Usage:
    python -m elt_pipeline.orchestrator --provider sofascore --seasons "2023/24"
    python -m elt_pipeline.orchestrator --provider api_football --seasons "2023/24"
"""

import sys
import gc
import signal
import logging
import argparse
import threading
from datetime import datetime
from typing import List, Optional, TypedDict

from providers.base.abstract_provider import AbstractDataProvider, AbstractDataTransformer
from providers.base.provider_registry import ProviderRegistry, discover_providers
from elt_pipeline.load.match_loader import MatchLoader
from elt_pipeline.transform.data_structures import ParsedMatchBundle
from utils.db_connector import DatabaseConnector
from utils.logging_config import setup_logging
from config.settings import get_config

logger = logging.getLogger(__name__)


# ── Result types ──────────────────────────────────────────────────────────────

class SeasonResult(TypedDict):
    season_name: str
    total: int
    success: int
    failed: int
    duration_seconds: float


class PipelineResult(TypedDict):
    success: bool
    provider: str
    total_seasons: int
    successful_seasons: int
    total_matches: int
    successful_matches: int
    duration_seconds: float
    season_results: List[SeasonResult]


# ── Orchestrator ──────────────────────────────────────────────────────────────

class ETLOrchestrator:
    """
    Coordinates Extract → Transform → Load for any data provider.

    Provider-agnostic: works with any AbstractDataProvider implementation.
    Transformer is resolved from registry matching the provider's name.
    """

    def __init__(
        self,
        provider: AbstractDataProvider,
        transformer: AbstractDataTransformer,
        batch_size: int = 50,
    ):
        self._provider = provider
        self._transformer = transformer
        self._batch_size = batch_size
        self._shutdown = threading.Event()

        logger.info(
            "ETLOrchestrator ready | provider='%s' | transformer='%s'",
            provider.name, transformer.provider_name,
        )
        assert provider.name == transformer.provider_name, (
            f"Provider '{provider.name}' and transformer '{transformer.provider_name}' mismatch! "
            "They must be from the same data source."
        )

    def request_shutdown(self) -> None:
        self._shutdown.set()
        logger.warning("Graceful shutdown requested.")

    def process_season(
        self,
        tournament_id: int,
        season_id: int,
        season_name: str,
    ) -> SeasonResult:
        """Extract → Transform → Load for one full season."""
        t_start = datetime.now()
        logger.info("=== Season %s (id=%d) via %s ===", season_name, season_id, self._provider.name)

        # ── 1. Provider health check ───────────────────────────────────────────
        if not self._provider.health_check():
            logger.critical("Provider '%s' health check failed. Aborting season.", self._provider.name)
            return self._result(season_name, 0, 0, 0, t_start)

        # ── 2. Extract match list ──────────────────────────────────────────────
        try:
            summaries = self._provider.fetch_season_matches(tournament_id, season_id)
        except NotImplementedError as e:
            logger.error("Provider method not implemented: %s", e)
            return self._result(season_name, 0, 0, 0, t_start)
        except Exception as e:
            logger.error("Failed to fetch season matches: %s", e, exc_info=True)
            return self._result(season_name, 0, 0, 0, t_start)

        if not summaries:
            logger.warning("No finished matches found for season %s.", season_name)
            return self._result(season_name, 0, 0, 0, t_start)

        logger.info("Found %d finished matches to process.", len(summaries))

        # ── 3. Extract + Transform each match ─────────────────────────────────
        parsed_bundles: List[ParsedMatchBundle] = []

        for i, summary in enumerate(summaries):
            if self._shutdown.is_set():
                logger.warning("Shutdown signal: stopping at match %d/%d.", i, len(summaries))
                break

            match_id = summary.external_id
            logger.info("[%d/%d] Processing match %d", i + 1, len(summaries), match_id)

            try:
                raw_bundle = self._provider.fetch_match_bundle(match_id)
                if not raw_bundle:
                    continue

                parsed = self._transformer.transform(raw_bundle)
                if parsed:
                    parsed_bundles.append(parsed)
                else:
                    logger.warning("Transform returned None for match %d.", match_id)

            except NotImplementedError as e:
                logger.error("Transformer not implemented: %s", e)
                break
            except Exception as e:
                logger.error("Error processing match %d: %s", match_id, e, exc_info=True)

            # Flush to DB in batches to manage memory
            if len(parsed_bundles) >= self._batch_size:
                self._load_batch(parsed_bundles)
                parsed_bundles.clear()
                gc.collect()

        # ── 4. Load remaining ──────────────────────────────────────────────────
        load_result = {"success": 0, "failed": 0, "total": 0}
        if parsed_bundles:
            load_result = self._load_batch(parsed_bundles)
            parsed_bundles.clear()

        gc.collect()
        return self._result(
            season_name,
            len(summaries),
            load_result.get("success", 0),
            load_result.get("failed", 0),
            t_start,
        )

    def _load_batch(self, bundles: List[ParsedMatchBundle]) -> dict:
        """Load a batch of bundles into DB via MatchLoader (full bundle - all tables)."""
        try:
            with DatabaseConnector.session_scope() as session:
                loader = MatchLoader(session)
                result = loader.bulk_load(bundles)
            logger.info("Batch loaded: %d success, %d failed.", result["success"], result["failed"])
            return result
        except Exception as e:
            logger.critical("Batch load failed: %s", e, exc_info=True)
            return {"success": 0, "failed": len(bundles), "total": len(bundles)}

    @staticmethod
    def _result(
        season_name: str, total: int, success: int, failed: int, t_start: datetime
    ) -> SeasonResult:
        return SeasonResult(
            season_name=season_name,
            total=total,
            success=success,
            failed=failed,
            duration_seconds=(datetime.now() - t_start).total_seconds(),
        )


# ── Pipeline runner ───────────────────────────────────────────────────────────

def run_pipeline(
    provider_name: str,
    specific_seasons: Optional[List[str]] = None,
) -> PipelineResult:
    t_start = datetime.now()
    result = PipelineResult(
        success=False, provider=provider_name,
        total_seasons=0, successful_seasons=0,
        total_matches=0, successful_matches=0,
        duration_seconds=0.0, season_results=[],
    )

    # Load all provider modules (triggers self-registration)
    discover_providers()

    config = get_config()

    if not ProviderRegistry.is_registered(provider_name):
        logger.critical("Provider '%s' not registered. Available: %s",
                        provider_name, ProviderRegistry.available_providers())
        return result

    provider = ProviderRegistry.create(provider_name, config)
    transformer = ProviderRegistry.create_transformer(provider_name)

    orchestrator = ETLOrchestrator(provider, transformer)

    # Wire graceful shutdown to orchestrator
    def _shutdown_handler(signum, frame):
        orchestrator.request_shutdown()

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    if not DatabaseConnector.check_connection():
        logger.critical("DB connection failed. Aborting pipeline.")
        return result

    # Resolve seasons to process
    all_seasons = config.get_target_seasons_with_ids()  # [(idx, name, season_id), ...]
    if specific_seasons:
        seasons = [s for s in all_seasons if s[1] in set(specific_seasons)]
    else:
        seasons = all_seasons

    if not seasons:
        logger.warning("No seasons to process.")
        result["success"] = True
        return result

    result["total_seasons"] = len(seasons)
    tournament_id = config.sofascore.premier_league_id

    for _, season_name, season_id in seasons:
        sr = orchestrator.process_season(tournament_id, season_id, season_name)
        result["season_results"].append(sr)
        result["total_matches"] += sr["total"]
        result["successful_matches"] += sr["success"]
        if sr["success"] > 0:
            result["successful_seasons"] += 1

    result["success"] = result["successful_seasons"] > 0
    result["duration_seconds"] = (datetime.now() - t_start).total_seconds()

    try:
        provider.close()
    except Exception:
        pass

    return result


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Provider-agnostic ELT Pipeline for football data.",
        epilog="Example: python -m elt_pipeline.orchestrator --provider sofascore",
    )
    parser.add_argument(
        "--provider", default="sofascore",
        help="Data provider to use (default: sofascore). "
             "Set PROVIDER in .env to override permanently.",
    )
    parser.add_argument("--seasons", nargs="+", metavar="SEASON",
                        help='Seasons to process, e.g. "2023/24" "2022/23"')
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    setup_logging(log_level=args.log_level)

    logger.info("=" * 60)
    logger.info("ELT Pipeline | Provider: %s", args.provider)
    logger.info("=" * 60)

    result = run_pipeline(args.provider, args.seasons)

    if result["success"]:
        logger.info("Pipeline completed. %d/%d matches loaded.",
                    result["successful_matches"], result["total_matches"])
        return 0
    else:
        logger.error("Pipeline failed. Check logs above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

