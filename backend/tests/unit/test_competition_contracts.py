"""Configuration and provider contracts that do not need a live network."""

from dataclasses import replace
from types import SimpleNamespace
import pytest
from config.competitions import get_competition
from football import parser


def test_calendar_and_cross_year_seasons_have_distinct_contracts():
    epl = get_competition()
    assert epl.season("2024/25") == ("2024/2025", 2024, 2025)
    calendar = replace(epl, season_format="calendar_year")
    assert calendar.season("2024") == ("2024", 2024, 2024)
    with pytest.raises(ValueError, match="does not match"):
        calendar.season("2024/2025")


def test_cli_count_and_explicit_seasons_are_mutually_exclusive():
    with pytest.raises(SystemExit) as result:
        parser().parse_args(["ingest", "--season-count", "3", "--seasons", "2024/2025"])
    assert result.value.code == 2


def test_provider_and_ingestion_count_changes_do_not_invalidate_feature_rules():
    epl = get_competition()
    assert replace(epl, providers={"sofascore": 17, "new_source": 12}, season_count=3).fingerprint == epl.fingerprint
    assert replace(epl, rounds=46).fingerprint != epl.fingerprint


def test_api_football_uses_its_own_seasons_and_regulation_scores(monkeypatch):
    import httpx
    from providers.api_football.provider import ApiFootballProvider
    from providers.api_football.transformer import ApiFootballTransformer
    monkeypatch.setenv("API_FOOTBALL_KEY", "contract-test-placeholder")
    settings = SimpleNamespace(read_timeout=5, connect_timeout=5, max_retries=1, min_delay=0, backoff_factor=1)
    provider = ApiFootballProvider(SimpleNamespace(scraping=settings, competition=get_competition()))
    provider._client.close()
    fixture = {"fixture": {"id": 123, "date": "2024-08-15T12:00:00+00:00", "timestamp": 1723723200,
        "status": {"short": "FT"}, "venue": {}},
        "league": {"id": 39, "name": "Premier League", "country": "England", "season": 2024, "round": "Regular Season - 1"},
        "teams": {"home": {"id": 10, "name": "Home"}, "away": {"id": 20, "name": "Away"}},
        "score": {"fulltime": {"home": 1, "away": 0}, "halftime": {"home": 0, "away": 0}}}
    def response(request):
        if request.url.path == "/leagues":
            data = [{"league": {"id": 39, "type": "League"}, "seasons": [{"year": 2024, "coverage": {}}]}]
        else:
            data = [fixture]
        return httpx.Response(200, json={"response": data, "errors": [], "paging": {"total": 1}})
    provider._client = httpx.Client(transport=httpx.MockTransport(response), base_url="https://provider.test")
    try:
        assert provider.list_seasons() == [("2024/2025", 2024)]
        assert len(provider.fetch_season_matches(39, 2024)) == 1
        transformed = ApiFootballTransformer().transform(provider.fetch_match_bundle(123))
        assert transformed.match.outcome.value == "H"
        assert transformed.match.season.external_id == 2024
        fixture["fixture"]["status"]["short"] = "AET"
        provider._fixtures.clear()
        with pytest.raises(ValueError, match="Extra time"):
            ApiFootballTransformer().transform(provider.fetch_match_bundle(123))
    finally:
        provider.close()
