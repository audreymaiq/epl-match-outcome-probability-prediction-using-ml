"""Season listings retain fixture status changes needed by the loader."""

from types import SimpleNamespace

from providers.sofascore.provider import SofaScoreProvider


def test_season_listing_keeps_cancelled_and_abandoned_fixtures():
    events = [
        {"id": index, "status": {"type": status}, "homeTeam": {"id": 1},
         "awayTeam": {"id": 2}, "startTimestamp": 1700000000 + index}
        for index, status in enumerate(
            ("finished", "notstarted", "inprogress", "postponed", "cancelled", "abandoned"),
            start=1,
        )
    ]
    provider = SofaScoreProvider.__new__(SofaScoreProvider)
    provider._breaker = None
    provider._extractor = SimpleNamespace(
        fetch_paginated_data=lambda **_: (events, None),
    )

    summaries = provider.fetch_season_matches(17, 1)

    assert {summary.status for summary in summaries} == {
        "finished", "notstarted", "inprogress", "postponed", "cancelled", "abandoned",
    }


def test_prematch_availability_requires_explicit_both_team_snapshots():
    import time
    from providers.base.components import ComponentStatus
    provider = SofaScoreProvider.__new__(SofaScoreProvider)
    provider._breaker = None
    provider._throttle = lambda: None
    provider._config = SimpleNamespace(sofascore=SimpleNamespace(prematch_hours=48))
    payload = {"home": {"players": []}, "away": {"players": []}}
    provider._extractor = SimpleNamespace(
        fetch_match_detail=lambda *a, **kw: {"event": {"status": {"type": "notstarted"}, "startTimestamp": time.time()+3600}},
        fetch_lineups=lambda *a, **kw: payload)
    assert provider.fetch_match_bundle(1).component_status["squad_availability"] == ComponentStatus.UNAVAILABLE
    payload["home"]["missingPlayers"] = []
    payload["away"]["missingPlayers"] = []
    result = provider.fetch_match_bundle(1)
    assert result.component_status["squad_availability"] == ComponentStatus.COMPLETE
    assert result.component_status["lineups"] == ComponentStatus.UNAVAILABLE
    assert result.component_status["events"] == ComponentStatus.NOT_REQUESTED
