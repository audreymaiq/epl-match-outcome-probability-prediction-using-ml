# providers/api_football/provider.py
"""
API-Football Data Provider - implementation template, not active.

This file demonstrates the Open/Closed principle:
  - The orchestrator, loader, and feature pipeline are UNCHANGED
  - Only this file needs to be implemented to add a new data source
  - Register only after all extraction and transformation methods work

HOW TO ACTIVATE:
  1. Implement each NotImplementedError method below
  2. Set PROVIDER=api_football in .env
  3. Register the provider and transformer, then restart the pipeline

API-Football docs: https://www.api-football.com/documentation-v3
"""

from __future__ import annotations

import logging
from typing import List, Optional, Any

from providers.base.abstract_provider import (
    AbstractDataProvider,
    AbstractDataTransformer,
    RawMatchBundle,
    RawMatchSummary,
)
from providers.base.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)

PROVIDER_NAME = "api_football"


class ApiFootballProvider(AbstractDataProvider):
    """
    API-Football.com provider.

    Endpoint mapping (analogous to SofaScore):
      SofaScore                    → API-Football
      ─────────────────────────────────────────────
      SEASON_MATCHES               → GET /fixtures?league=39&season={year}
      MATCH_DETAIL                 → GET /fixtures?id={id}
      MATCH_INCIDENTS (goals/cards)→ GET /fixtures/events?fixture={id}
      MATCH_LINEUPS                → GET /fixtures/lineups?fixture={id}
      MATCH_STATISTICS             → GET /fixtures/statistics?fixture={id}

    EPL league ID on API-Football: 39
    """

    def __init__(self, config):
        self._config = config
        # API-Football uses Bearer token auth
        # self._api_key = config.api_football.get_random_key()

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    @property
    def tournament_id(self) -> int:
        return 39

    def list_seasons(self) -> List[tuple[str, int]]:
        raise NotImplementedError("Map EPL season names to API-Football season years.")

    def health_check(self) -> bool:
        """Ping API-Football status endpoint."""
        raise NotImplementedError(
            "ApiFootballProvider.health_check() not yet implemented. "
            "See providers/api_football/provider.py for implementation guide."
        )

    def fetch_season_matches(
        self,
        tournament_id: int,
        season_id: int,
    ) -> List[RawMatchSummary]:
        """
        Fetch all finished matches for a season.

        API-Football uses year (e.g. 2023) as season identifier,
        not an opaque season_id like SofaScore.
        The season_id passed here is the SofaScore ID - the implementation
        should derive the year from it or use a separate mapping.

        Returns:
            List of RawMatchSummary (provider-agnostic).
        """
        raise NotImplementedError(
            "ApiFootballProvider.fetch_season_matches() not yet implemented."
        )

    def fetch_match_bundle(
        self,
        match_id: int,
        include_lineups: bool = True,
        include_statistics: bool = True,
    ) -> Optional[RawMatchBundle]:
        """
        Fetch full data bundle for one match.
        map API-Football fixture ID → match_id.
        """
        raise NotImplementedError(
            "ApiFootballProvider.fetch_match_bundle() not yet implemented."
        )


class ApiFootballTransformerAdapter(AbstractDataTransformer):
    """
    Transforms API-Football raw bundles to ParsedMatchBundle.

    When implementing: create an ApiFootballTransformer (analogous to
    SofaScoreTransformer) that handles API-Football's JSON structure.
    The field names differ but the canonical output is identical.
    """

    @property
    def provider_name(self) -> str:
        return PROVIDER_NAME

    def transform(self, raw_bundle: RawMatchBundle) -> Optional[Any]:
        raise NotImplementedError(
            "ApiFootballTransformerAdapter.transform() not yet implemented."
        )


# Register this pair only after its contract tests pass:
# ProviderRegistry.register(PROVIDER_NAME, ApiFootballProvider, ApiFootballTransformerAdapter)
