"""Provider payloads must retain their pre-match and in-play semantics."""

from copy import deepcopy

import pytest


def _bundle(status: str, home_score=1, away_score=0):
    return {
        "details": {"event": {
            "id": 123456,
            "tournament": {
                "uniqueTournament": {"id": 17, "name": "Premier League"},
                "category": {"name": "England"},
            },
            "season": {"id": 61627, "year": "2024/25"},
            "homeTeam": {"id": 1, "name": "Arsenal"},
            "awayTeam": {"id": 2, "name": "Chelsea"},
            "startTimestamp": 1735743600,
            "roundInfo": {"round": 20},
            "status": {"type": status},
            "homeScore": {"current": home_score},
            "awayScore": {"current": away_score},
        }},
        "lineups": {
            "home": {"players": [{
                "player": {"id": 11, "name": "Home player", "position": "F"},
                "shirtNumber": 9,
                "substitute": False,
            }]},
            "away": {"missingPlayers": [{
                "player": {"id": 22, "name": "Away player"},
                "type": "missing",
            }]},
        },
    }


def test_in_progress_score_has_no_final_outcome_and_keeps_lineups():
    pytest.importorskip("pydantic")
    from elt_pipeline.transform.sofascore_transformer import SofaScoreTransformer

    result = SofaScoreTransformer().transform_match_bundle(_bundle("inprogress"))

    assert result is not None
    assert result.match.outcome is None
    assert result.match.match_week == "20"
    assert len(result.lineups) == 1
    assert result.lineups[0].team.external_id == 1
    assert len(result.squad_availability) == 1
    assert result.squad_availability[0].team.external_id == 2


def test_finished_match_needs_a_final_score():
    pytest.importorskip("pydantic")
    from config.core_constants import MatchOutcome
    from elt_pipeline.transform.sofascore_transformer import SofaScoreTransformer

    transformer = SofaScoreTransformer()
    assert transformer.transform_match_bundle(_bundle("finished")).match.outcome == MatchOutcome.H

    missing_score = deepcopy(_bundle("finished"))
    missing_score["details"]["event"]["awayScore"] = {}
    assert transformer.transform_match_bundle(missing_score) is None
