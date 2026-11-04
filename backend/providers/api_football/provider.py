"""API-SPORTS v3 adapter. Contract: https://www.api-football.com/documentation_v3."""

import os
import time
import httpx
from config.competitions import get_competition
from providers.base.abstract_provider import AbstractDataProvider, RawMatchSummary, RawMatchBundle
from providers.base.components import ComponentStatus
from providers.base.errors import ProviderUnavailableError
from providers.base.provider_registry import ProviderRegistry
from providers.api_football.transformer import ApiFootballTransformer


class ApiFootballProvider(AbstractDataProvider):
    name = "api_football"

    def __init__(self, config):
        self.competition = getattr(config, "competition", None) or get_competition()
        if self.name not in self.competition.providers:
            raise ValueError("API-Football tournament ID is not configured")
        key = os.getenv("API_FOOTBALL_KEY")
        if not key:
            raise ValueError("API_FOOTBALL_KEY is required")
        self._max_requests = int(os.getenv("API_FOOTBALL_MAX_REQUESTS", "1000"))
        if self._max_requests < 1:
            raise ValueError("API_FOOTBALL_MAX_REQUESTS must be positive")
        self._settings = config.scraping
        self._client = httpx.Client(base_url="https://v3.football.api-sports.io",
            headers={"x-apisports-key": key},
            timeout=httpx.Timeout(self._settings.read_timeout, connect=self._settings.connect_timeout))
        self._coverage = {}
        self._fixtures = {}
        self._request_count = 0

    @property
    def tournament_id(self):
        return self.competition.providers[self.name]

    def _get(self, path, **params):
        for attempt in range(self._settings.max_retries):
            if self._request_count >= self._max_requests:
                raise ProviderUnavailableError("API-Football request budget exhausted")
            if self._request_count:
                time.sleep(self._settings.min_delay)
            self._request_count += 1
            try:
                response = self._client.get(path, params=params)
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    raise ProviderUnavailableError(f"API-Football rejected access with HTTP {response.status_code}")
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt+1 < self._settings.max_retries:
                        time.sleep(min(self._settings.backoff_factor ** attempt, 30))
                        continue
                response.raise_for_status()
            except httpx.TransportError:
                if attempt+1 == self._settings.max_retries:
                    raise RuntimeError("API-Football transport failed") from None
                time.sleep(min(self._settings.backoff_factor ** attempt, 30))
                continue
            data = response.json()
            if not isinstance(data, dict) or data.get("errors"):
                raise ProviderUnavailableError("API-Football reported an API error; check credentials, subscription and quota")
            if not isinstance(data.get("response"), list):
                raise ValueError("Invalid API-Football response envelope")
            paging = data.get("paging", {})
            if paging.get("total", 1) != 1:
                raise ValueError("Unexpected paginated fixture response; incomplete ingestion refused")
            return data["response"]
        raise RuntimeError("API-Football retry budget exhausted")

    def list_seasons(self):
        entries = self._get("/leagues", id=self.tournament_id)
        if len(entries) != 1 or entries[0]["league"]["id"] != self.tournament_id or entries[0]["league"]["type"] != "League":
            raise ValueError("Expected one configured national league")
        seasons = []
        for season in entries[0]["seasons"]:
            year = int(season["year"])
            name, _, _ = self.competition.season(str(year))
            seasons.append((name, year))
            self._coverage[year] = season.get("coverage", {}).get("fixtures", {})
        if not seasons:
            raise ValueError("Provider returned no available seasons")
        return sorted(set(seasons), reverse=True)

    def fetch_season_matches(self, tournament_id, season_id):
        fixtures = self._get("/fixtures", league=tournament_id, season=season_id, timezone="UTC")
        self._fixtures = {item["fixture"]["id"]: item for item in fixtures}
        if len(self._fixtures) != len(fixtures):
            raise ValueError("Duplicate fixture IDs in source response")
        summaries = []
        for item in fixtures:
            fixture, teams = item["fixture"], item["teams"]
            summaries.append(RawMatchSummary(fixture["id"], fixture["status"]["short"],
                teams["home"]["id"], teams["away"]["id"], fixture.get("timestamp"), None, item))
        return sorted(summaries, key=lambda item: item.start_timestamp or 0)

    def fetch_match_bundle(self, match_id, include_lineups=True, include_statistics=True):
        item = self._fixtures.get(match_id)
        if item is None:
            entries = self._get("/fixtures", id=match_id, timezone="UTC")
            if len(entries) != 1:
                raise ValueError(f"Fixture {match_id} not found")
            item = entries[0]
        if item["league"]["id"] != self.tournament_id:
            raise ValueError("Fixture belongs to a different competition")
        coverage = self._coverage.get(int(item["league"]["season"]), {})
        status = {name: ComponentStatus.NOT_REQUESTED for name in (
            "events", "lineups", "squad_availability", "player_stats", "team_stats")}
        parts = {}
        for name, endpoint, enabled, covered in (
            ("events", "/fixtures/events", True, coverage.get("events", False)),
            ("lineups", "/fixtures/lineups", include_lineups, coverage.get("lineups", False)),
            ("team_stats", "/fixtures/statistics", include_statistics, coverage.get("statistics_fixtures", False)),
        ):
            if not enabled or item["fixture"]["status"]["short"] != "FT":
                parts[name] = {}
            elif not covered:
                parts[name] = {}
                status[name] = ComponentStatus.UNAVAILABLE
            else:
                values = self._get(endpoint, fixture=match_id)
                parts[name] = {"response": values}
                # Coverage + an empty event list can legitimately mean no events.
                # Empty lineups/statistics are unavailable, not authoritative deletion.
                status[name] = ComponentStatus.COMPLETE if values or name == "events" else ComponentStatus.UNAVAILABLE
                if values and name in {"lineups", "team_stats"}:
                    expected = {item["teams"][side]["id"] for side in ("home", "away")}
                    actual = {entry.get("team", {}).get("id") for entry in values}
                    if actual != expected or len(values) != 2:
                        status[name] = ComponentStatus.PARTIAL
        return RawMatchBundle(match_id, item, parts["events"], parts["lineups"], parts["team_stats"], self.name, status)

    def close(self):
        self._client.close()


ProviderRegistry.register("api_football", ApiFootballProvider, ApiFootballTransformer)
