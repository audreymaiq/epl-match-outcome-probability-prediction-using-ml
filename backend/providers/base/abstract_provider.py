# providers/base/abstract_provider.py
"""
Abstract Data Provider Interface.

Design principle: Dependency Inversion (SOLID - D)
- High-level modules (orchestrator, pipeline) depend on THIS abstraction
- NOT on SofaScore, API-Football, or any concrete provider

To add a new provider:
  1. Create providers/<name>/provider.py
  2. Implement AbstractDataProvider
  3. Register in ProviderRegistry
  4. Set PROVIDER=<name> in .env

Nothing else changes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Any


# ── Provider-agnostic raw data contracts ─────────────────────────────────────
# These DTOs are the "universal language" between providers and the pipeline.
# Each provider maps its own API response → these models.

@dataclass
class RawMatchSummary:
    """Minimal match info from a season listing endpoint."""
    external_id: int
    status: str                     # "finished", "scheduled", "postponed", etc.
    home_team_external_id: int
    away_team_external_id: int
    start_timestamp: Optional[int]
    round_number: Optional[int]
    raw: Dict[str, Any] = field(default_factory=dict)  # Original response preserved


@dataclass
class RawMatchBundle:
    """
    Full raw data bundle for one match.
    All fields are Optional - providers may not have every data point.
    The transformer validates and fills in defaults.
    """
    external_id: int
    detail: Dict[str, Any]          # Full match detail from provider
    incidents: Dict[str, Any]       # Goals, cards, substitutions
    lineups: Dict[str, Any]         # Starting XIs, substitutes, missing players
    statistics: Dict[str, Any]      # Shots, possession, xG, etc.
    provider_name: str              # "sofascore", "api_football", etc.

    def is_complete(self) -> bool:
        """True if all 4 data sources are present (non-empty)."""
        return all([self.detail, self.incidents, self.lineups, self.statistics])

    def completeness_score(self) -> float:
        """0.0 to 1.0 - how complete this bundle is."""
        parts = [self.detail, self.incidents, self.lineups, self.statistics]
        return sum(1 for p in parts if p) / len(parts)


# ── Abstract Provider Interface ───────────────────────────────────────────────

class AbstractDataProvider(ABC):
    """
    Contract that every data provider must fulfill.

    Implementations: SofaScoreProvider, ApiFootballProvider, FBRefProvider, etc.
    The orchestrator depends ONLY on this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this provider, e.g. 'sofascore'."""

    @property
    @abstractmethod
    def tournament_id(self) -> int:
        """Provider-specific EPL tournament identifier."""

    @abstractmethod
    def list_seasons(self) -> List[tuple[str, int]]:
        """Available (canonical season name, provider season ID) pairs, newest first."""

    @abstractmethod
    def fetch_season_matches(
        self,
        tournament_id: int,
        season_id: int,
    ) -> List[RawMatchSummary]:
        """
        Fetch all match summaries for a given season.
        Returns list of RawMatchSummary, sorted chronologically.
        Include upcoming fixtures and status changes; training selects FINISHED matches.
        """

    @abstractmethod
    def fetch_match_bundle(
        self,
        match_id: int,
        include_lineups: bool = True,
        include_statistics: bool = True,
    ) -> Optional[RawMatchBundle]:
        """
        Fetch the full data bundle for a single match.
        Returns None if the match is unavailable or fails.
        `include_lineups` and `include_statistics` allow partial fetches
        when saving requests is necessary (rate limit).
        """

    def health_check(self) -> bool:
        """
        Optional: verify the provider is reachable.
        Default implementation returns True (provider doesn't support health check).
        Override in concrete implementations.
        """
        return True

    def close(self) -> None:
        """Cleanup resources (sessions, connections). Override if needed."""
        pass


# ── Abstract Transformer Interface ────────────────────────────────────────────

class AbstractDataTransformer(ABC):
    """
    Contract for transforming provider-specific raw data
    into the canonical internal representation (ParsedMatchBundle).

    One transformer per provider - they know the provider's quirks.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Must match the provider's .name property."""

    @abstractmethod
    def transform(self, raw_bundle: RawMatchBundle) -> Optional[Any]:
        """
        Transform RawMatchBundle → ParsedMatchBundle.
        Returns None if transformation fails (log the reason).
        Import ParsedMatchBundle locally to avoid circular imports.
        """

