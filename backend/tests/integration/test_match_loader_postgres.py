"""Exercise the real match loader against PostgreSQL without retaining test data."""

import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest


def test_match_bundle_is_atomic_and_idempotent_on_postgres():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run the PostgreSQL integration test")

    sqlalchemy = pytest.importorskip("sqlalchemy")
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from config.core_constants import (
        MatchEventType, MatchOutcome, MatchPeriod, MatchStatus, PlayerStatus,
    )
    from elt_pipeline.load.match_loader import MatchLoader
    from elt_pipeline.transform.data_structures import (
        ParsedLeague, ParsedLineup, ParsedMatch, ParsedMatchBundle,
        ParsedMatchEvent, ParsedMatchPlayerStats, ParsedMatchTeamStats,
        ParsedPlayer, ParsedSeason, ParsedSquadAvailability, ParsedTeam,
    )

    unique_id = uuid4().int % 1_000_000_000
    suffix = str(unique_id)
    league = ParsedLeague(unique_id, f"Integration league {suffix}", "England")
    season = ParsedSeason(unique_id + 1, f"2024/25 integration {suffix}", 2024, 2025, league)
    home = ParsedTeam(unique_id + 2, f"Integration home {suffix}")
    away = ParsedTeam(unique_id + 3, f"Integration away {suffix}")
    player = ParsedPlayer(unique_id + 4, f"Integration player {suffix}")
    absent_player = ParsedPlayer(unique_id + 5, f"Integration absent {suffix}")
    match = ParsedMatch(
        external_id=unique_id + 6,
        season=season,
        match_datetime=datetime(2025, 1, 1, 15, tzinfo=timezone.utc),
        match_week="20",
        home_team=home,
        away_team=away,
        stadium=None,
        referee=None,
        status=MatchStatus.FINISHED,
        outcome=MatchOutcome.H,
        home_goals=1,
        away_goals=0,
        half_time_home_goals=1,
        half_time_away_goals=0,
        attendance=10000,
    )
    bundle = ParsedMatchBundle(
        match=match,
        events=[ParsedMatchEvent(12, MatchEventType.GOAL, home, player, None,
                                 MatchPeriod.FIRST_HALF)],
        lineups=[ParsedLineup(player, home, True, 9, False, "FWD")],
        squad_availability=[ParsedSquadAvailability(absent_player, away,
                                                     PlayerStatus.INJURED)],
        player_stats=[ParsedMatchPlayerStats(player, home, True, 90, goals=1,
                                             passes=10, accurate_passes=8)],
        team_stats=[ParsedMatchTeamStats(home, Decimal("55.00"), total_shots=10),
                    ParsedMatchTeamStats(away, Decimal("45.00"), total_shots=5)],
    )

    engine = sqlalchemy.create_engine(database_url)
    try:
        with Session(engine) as session:
            session.begin()
            try:
                loader = MatchLoader(session)
                match_id = loader.load_bundle(bundle)
                assert loader.load_bundle(bundle) == match_id
                for table, expected in (
                    ("MatchEvents", 1), ("Lineups", 1),
                    ("SquadAvailability", 1), ("MatchPlayerStats", 1),
                    ("MatchTeamStats", 2),
                ):
                    count = session.execute(
                        text(f'SELECT COUNT(*) FROM "{table}" WHERE match_id = :id'),
                        {"id": match_id},
                    ).scalar_one()
                    assert count == expected, table

                invalid_match = replace(
                    match,
                    external_id=unique_id + 7,
                    match_datetime=match.match_datetime + timedelta(days=7),
                )
                invalid_bundle = ParsedMatchBundle(
                    match=invalid_match,
                    lineups=[ParsedLineup(player, home, True, -1, False, "FWD")],
                )
                with pytest.raises(sqlalchemy.exc.IntegrityError):
                    loader.load_bundle(invalid_bundle)

                assert session.execute(
                    text('SELECT COUNT(*) FROM "Matches" WHERE id = :id'),
                    {"id": match_id},
                ).scalar_one() == 1
                assert session.execute(
                    text('SELECT COUNT(*) FROM "ExternalMapping" '
                         "WHERE external_id = :id AND entity_type = 'match'"),
                    {"id": str(invalid_match.external_id)},
                ).scalar_one() == 0
            finally:
                session.rollback()
    finally:
        engine.dispose()
