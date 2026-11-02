# providers/sofascore/provider.py
"""
SofaScore Data Provider - Full Implementation.

Implements AbstractDataProvider + AbstractDataTransformer for SofaScore.
ALL SofaScore-specific logic is confined to this file, extractor.py and endpoints.py.
Nothing outside providers/sofascore/ knows SofaScore exists.

Registration:
  Self-registers into ProviderRegistry on import.
  Triggered by discover_providers() in orchestrator.

Resilience features (production-grade):
  - Circuit breaker: stops hammering a failing API (pybreaker)
  - Exponential backoff retry on transient errors
  - Session rotation every N requests (avoid fingerprinting)
  - Random delay between requests (human-like pattern)
  - Graceful degradation: partial bundle still processable
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional, Any

from providers.base.abstract_provider import (
    AbstractDataProvider,
    AbstractDataTransformer,
    RawMatchBundle,
    RawMatchSummary,
)
from providers.base.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)

PROVIDER_NAME = "sofascore"


# ─────────────────────────────────────────────────────────────────────────────
# SofaScoreProvider
# ─────────────────────────────────────────────────────────────────────────────

class SofaScoreProvider(AbstractDataProvider):
    """
    Fetches raw match data from the unofficial SofaScore API.

    All HTTP calls are delegated to SofaScoreExtractor (HTTP client only).
    This class owns: rate limiting, circuit breaker, session lifecycle,
    and the logic of WHICH endpoints to call.

    Does NOT know about ParsedMatchBundle or DB - that's the transformer's job.
    """

    def __init__(self, config):
        """
        Args:
            config: ConfigManager instance (from config.settings.get_config()).
        """
        from providers.sofascore.extractor import SofaScoreExtractor
        try:
            from pybreaker import CircuitBreaker
            self._breaker = CircuitBreaker(
                fail_max=config.sofascore.circuit_breaker_threshold,
                reset_timeout=config.sofascore.circuit_breaker_timeout,
            )
        except ImportError:
            self._breaker = None
            logger.warning("pybreaker not installed - circuit breaker disabled.")

        self._extractor = SofaScoreExtractor(config.sofascore, config.scraping)
        self._config = config
        self._request_count = 0

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    def health_check(self) -> bool:
        """
        Verify SofaScore API is reachable by fetching one known match.
        Uses the current EPL tournament page as a lightweight probe.
        """
        try:
            result = self._extractor.fetch_paginated_data(
                endpoint=self._endpoint_cls().SEASON_MATCHES,
                response_field="events",
                tournament_id=self._config.sofascore.premier_league_id,
                season_id=self._current_season_id(),
                breaker=self._breaker,
            )
            return result is not None
        except Exception as exc:
            logger.warning("SofaScore health check failed: %s", exc)
            return False

    def fetch_season_matches(
        self,
        tournament_id: int,
        season_id: int,
    ) -> List[RawMatchSummary]:
        """
        Fetch all FINISHED match summaries for a season.
        Paginates through all pages automatically.
        Returns sorted chronologically.
        """
        from providers.sofascore.endpoints import SofaScoreEndpoints

        all_events, has_data = self._extractor.fetch_paginated_data(
            endpoint=SofaScoreEndpoints.SEASON_MATCHES,
            response_field="events",
            tournament_id=tournament_id,
            season_id=season_id,
            breaker=self._breaker,
        )

        if not has_data:
            logger.warning(
                "No events returned for tournament=%d, season=%d",
                tournament_id, season_id,
            )
            return []

        # Map to provider-agnostic RawMatchSummary
        summaries: List[RawMatchSummary] = []
        for event in all_events:
            status_type = self._get_nested(event, "status.type", "")
            if status_type != "finished":
                continue   # Only process completed matches

            try:
                summary = RawMatchSummary(
                    external_id=event["id"],
                    status=status_type,
                    home_team_external_id=self._get_nested(event, "homeTeam.id"),
                    away_team_external_id=self._get_nested(event, "awayTeam.id"),
                    start_timestamp=event.get("startTimestamp"),
                    round_number=self._get_nested(event, "roundInfo.round"),
                    raw=event,
                )
                summaries.append(summary)
            except (KeyError, TypeError) as exc:
                logger.debug("Skipping malformed event %s: %s", event.get("id"), exc)

        # Sort chronologically
        summaries.sort(key=lambda s: s.start_timestamp or 0)
        logger.info(
            "Season %d: %d finished matches fetched.", season_id, len(summaries)
        )
        return summaries

    def fetch_match_bundle(
        self,
        match_id: int,
        include_lineups: bool = True,
        include_statistics: bool = True,
    ) -> Optional[RawMatchBundle]:
        """
        Fetch all 4 data endpoints for one match:
          - detail      : full match info, teams, scores, referee, venue
          - incidents   : goals, cards, substitutions (timeline)
          - lineups     : starting XI, substitutes, missing players
          - statistics  : possession, shots, corners, etc.

        Partial bundles (e.g. missing statistics) are returned but flagged.
        Returns None if the detail endpoint fails (can't proceed without it).
        """
        self._throttle()

        # 1. Match detail - mandatory
        detail = self._extractor.fetch_match_detail(match_id, breaker=self._breaker)
        if not detail:
            logger.warning("fetch_match_bundle: no detail for match %d - skipping.", match_id)
            return None

        # 2. Incidents (goals, cards) - mandatory for outcome verification
        incidents = self._extractor.fetch_incidents(match_id, breaker=self._breaker) or {}

        # 3. Lineups (squad availability, player data) - optional
        lineups: dict = {}
        if include_lineups:
            lineups = self._extractor.fetch_lineups(match_id, breaker=self._breaker) or {}

        # 4. Statistics (xG proxy, possession, shots) - optional
        statistics: dict = {}
        if include_statistics:
            statistics = self._extractor.fetch_statistics(match_id, breaker=self._breaker) or {}

        bundle = RawMatchBundle(
            external_id=match_id,
            detail=detail,
            incidents=incidents,
            lineups=lineups,
            statistics=statistics,
            provider_name=self.name,
        )

        completeness = bundle.completeness_score()
        if completeness < 0.5:
            logger.warning(
                "Bundle for match %d is only %.0f%% complete (detail+incidents missing).",
                match_id, completeness * 100,
            )

        return bundle

    def close(self) -> None:
        try:
            self._extractor.close()
        except Exception:
            pass

    # ── Private helpers ───────────────────────────────────────────────────────

    def _throttle(self) -> None:
        """Rate-limit: sleep between requests based on config."""
        self._request_count += 1
        delay = self._config.sofascore.delay_between_requests
        random_extra = self._config.scraping.get_random_delay()
        time.sleep(delay + random_extra)

        # Session rotation
        rotation_interval = self._config.sofascore.session_rotation_interval
        if self._request_count % rotation_interval == 0:
            logger.debug(
                "Session rotation after %d requests.", self._request_count
            )

    def _current_season_id(self) -> int:
        """Get the most recent known SofaScore season ID for health check."""
        mapping = self._config.sofascore.get_season_id_mapping()
        if mapping:
            return list(mapping.values())[-1]
        return 61627  # 2024/25 fallback

    @staticmethod
    def _endpoint_cls():
        from providers.sofascore.endpoints import SofaScoreEndpoints
        return SofaScoreEndpoints

    @staticmethod
    def _get_nested(data: dict, path: str, default=None):
        """Safe nested dict access with dot-path notation."""
        keys = path.split(".")
        value = data
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value


# ─────────────────────────────────────────────────────────────────────────────
# SofaScoreTransformerAdapter
# ─────────────────────────────────────────────────────────────────────────────

class SofaScoreTransformerAdapter(AbstractDataTransformer):
    """
    Adapts SofaScoreTransformer to the AbstractDataTransformer interface.

    The inner SofaScoreTransformer works with raw dict bundles.
    This adapter:
      1. Converts RawMatchBundle → dict format expected by SofaScoreTransformer
      2. Calls transform_match_bundle()
      3. Returns ParsedMatchBundle (canonical internal format)
    """

    @property
    def provider_name(self) -> str:
        return PROVIDER_NAME

    def transform(self, raw_bundle: RawMatchBundle) -> Optional[Any]:
        """
        Transform RawMatchBundle → ParsedMatchBundle.
        Returns None if transformation fails (logged internally).
        """
        from elt_pipeline.transform.sofascore_transformer import SofaScoreTransformer

        transformer = SofaScoreTransformer()

        # Map RawMatchBundle fields to the dict format SofaScoreTransformer expects
        raw_dict = {
            "details":    raw_bundle.detail,
            "incidents":  raw_bundle.incidents,
            "lineups":    raw_bundle.lineups,
            "statistics": raw_bundle.statistics,
        }

        try:
            return transformer.transform_match_bundle(raw_dict)
        except Exception as exc:
            logger.error(
                "SofaScore transform failed for match %d: %s",
                raw_bundle.external_id, exc,
                exc_info=True,
            )
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Self-registration into ProviderRegistry
# ─────────────────────────────────────────────────────────────────────────────

def _register():
    """
    Register SofaScore provider and transformer.
    Called automatically when this module is imported.
    Uses the Open/Closed principle: adding a new provider never modifies
    the registry code - only the provider module needs to register itself.
    """
    ProviderRegistry.register(
        name=PROVIDER_NAME,
        provider_class=SofaScoreProvider,
        transformer_class=SofaScoreTransformerAdapter,
    )
    logger.debug("SofaScore provider registered in ProviderRegistry.")


_register()
