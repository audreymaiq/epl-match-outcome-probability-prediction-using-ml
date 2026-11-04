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
from config.core_constants import MatchStatus, get_match_status_from_sofascore

logger = logging.getLogger(__name__)

from config.competitions import get_competition
from providers.base.components import ComponentStatus

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
        self.competition = getattr(config, "competition", None) or get_competition()
        self._request_count = 0

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    @property
    def tournament_id(self) -> int:
        competition = getattr(self, "competition", None) or get_competition()
        if self.name not in competition.providers:
            raise ValueError(f"No {self.name} tournament configured for {competition.slug}")
        return competition.providers[self.name]

    def list_seasons(self) -> List[tuple[str, int]]:
        """Resolve season IDs from the provider instead of a dated local table."""
        if hasattr(self, "_seasons"):
            return self._seasons
        response = self._extractor.fetch_seasons(self.tournament_id, breaker=self._breaker)
        if not response or not isinstance(response.get("seasons"), list):
            raise RuntimeError("SofaScore did not return an EPL season catalogue.")
        seasons: List[tuple[str, int]] = []
        for item in response["seasons"]:
            year = item.get("year", "")
            try:
                competition = getattr(self, "competition", None) or get_competition()
                season_name, _, _ = competition.season(year)
                season_id = int(item["id"])
                if season_id > 0:
                    seasons.append((season_name, season_id))
            except (KeyError, TypeError, ValueError):
                logger.warning("Ignoring malformed SofaScore season: %s", item)
        if not seasons:
            raise RuntimeError("SofaScore returned no usable EPL seasons.")
        self._seasons = sorted(seasons, key=lambda season: season[0], reverse=True)
        return self._seasons

    def health_check(self) -> bool:
        """
        Verify the EPL season catalogue is available.
        """
        try:
            return bool(self.list_seasons())
        except Exception as exc:
            logger.warning("SofaScore health check failed: %s", exc)
            return False

    def fetch_season_matches(
        self,
        tournament_id: int,
        season_id: int,
    ) -> List[RawMatchSummary]:
        """
        Fetch completed and upcoming fixtures, including terminal status changes.
        Paginates through all pages automatically.
        Returns sorted chronologically.
        """
        from providers.sofascore.endpoints import SofaScoreEndpoints

        all_events = []
        for endpoint in (SofaScoreEndpoints.SEASON_MATCHES_LAST, SofaScoreEndpoints.SEASON_MATCHES_NEXT):
            events, _ = self._extractor.fetch_paginated_data(
                endpoint=endpoint,
                response_field="events",
                tournament_id=tournament_id,
                season_id=season_id,
                breaker=self._breaker,
            )
            all_events.extend(events)

        if not all_events:
            logger.warning(
                "No events returned for tournament=%d, season=%d",
                tournament_id, season_id,
            )
            return []

        # Map to provider-agnostic RawMatchSummary
        summaries: List[RawMatchSummary] = []
        seen_ids = set()
        for event in all_events:
            status_type = self._get_nested(event, "status.type", "")
            if get_match_status_from_sofascore(status_type) not in {
                MatchStatus.FINISHED,
                MatchStatus.SCHEDULED,
                MatchStatus.IN_PROGRESS,
                MatchStatus.POSTPONED,
                MatchStatus.CANCELLED,
                MatchStatus.ABANDONED,
            }:
                continue

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
                if summary.external_id not in seen_ids:
                    summaries.append(summary)
                    seen_ids.add(summary.external_id)
            except (KeyError, TypeError) as exc:
                logger.debug("Skipping malformed event %s: %s", event.get("id"), exc)

        # Sort chronologically
        summaries.sort(key=lambda s: s.start_timestamp or 0)
        logger.info(
            "Season %d: %d matches and fixtures fetched.", season_id, len(summaries)
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

        is_finished = self._get_nested(detail, "event.status.type") == "finished"
        kickoff = self._get_nested(detail, "event.startTimestamp")
        prematch = kickoff is not None and 0 <= kickoff-time.time() <= self._config.sofascore.prematch_hours*3600

        # 2. Match statistics are not available before kickoff.
        incidents = (self._extractor.fetch_incidents(match_id, breaker=self._breaker) or {}) if is_finished else {}

        # 3. Lineups (squad availability, player data) - optional
        lineups: dict = {}
        if include_lineups and (is_finished or prematch):
            lineups = self._extractor.fetch_lineups(match_id, breaker=self._breaker) or {}

        # 4. Statistics (xG proxy, possession, shots) - optional
        statistics: dict = {}
        if include_statistics and is_finished:
            statistics = self._extractor.fetch_statistics(match_id, breaker=self._breaker) or {}

        sides = [lineups.get(side, {}) for side in ("home", "away")]
        lineup_complete = all(isinstance(side.get("players"), list) and side["players"] for side in sides)
        availability_complete = all(isinstance(side.get("missingPlayers"), list) for side in sides)
        player_stats_complete = is_finished and lineup_complete and all(
            isinstance(player.get("statistics"), dict) for side in sides for player in side["players"])
        all_statistics = next((part for part in statistics.get("statistics", []) if part.get("period") == "ALL"), None)
        not_requested = ComponentStatus.NOT_REQUESTED
        unavailable = ComponentStatus.UNAVAILABLE
        bundle = RawMatchBundle(
            external_id=match_id,
            detail=detail,
            incidents=incidents,
            lineups=lineups,
            statistics=statistics,
            provider_name=self.name,
            component_status={
                "events": ComponentStatus.COMPLETE if isinstance(incidents.get("incidents"), list) else unavailable if is_finished else not_requested,
                "lineups": ComponentStatus.COMPLETE if lineup_complete else unavailable if include_lineups and (is_finished or prematch) else not_requested,
                "squad_availability": ComponentStatus.COMPLETE if availability_complete else unavailable if include_lineups and (is_finished or prematch) else not_requested,
                "player_stats": ComponentStatus.COMPLETE if player_stats_complete else unavailable if include_lineups and is_finished else not_requested,
                "team_stats": ComponentStatus.COMPLETE if all_statistics and all_statistics.get("groups") else unavailable if include_statistics and is_finished else not_requested,
            },
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

        transformer = SofaScoreTransformer(getattr(self, "competition", None))

        # Map RawMatchBundle fields to the dict format SofaScoreTransformer expects
        raw_dict = {
            "details":    raw_bundle.detail,
            "incidents":  raw_bundle.incidents,
            "lineups":    raw_bundle.lineups,
            "statistics": raw_bundle.statistics,
        }

        try:
            parsed = transformer.transform_match_bundle(raw_dict)
            if parsed is not None:
                parsed.component_status = dict(raw_bundle.component_status)
                parsed.raw_payload = raw_dict
                for component, status in parsed.component_status.items():
                    if status != ComponentStatus.COMPLETE:
                        setattr(parsed, component, [])
                if parsed.match.season.league.external_id != transformer.competition.providers[self.provider_name]:
                    raise ValueError("Fixture belongs to a different tournament")
            return parsed
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
