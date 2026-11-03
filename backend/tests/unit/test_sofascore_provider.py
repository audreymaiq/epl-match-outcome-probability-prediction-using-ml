"""Season listings retain fixture status changes needed by the loader."""

from types import SimpleNamespace

from providers.sofascore.provider import SofaScoreProvider


def test_season_listing_keeps_cancelled_and_abandoned_fixtures():
    events = [
        {"id": index, "status": {"type": status}, "homeTeam": {"id": 1},
         "awayTeam": {"id": 2}, "startTimestamp": 1700000000 + index}
        for index, status in enumerate(
            ("finished", "notstarted", "postponed", "cancelled", "abandoned"),
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
        "finished", "notstarted", "postponed", "cancelled", "abandoned",
    }
