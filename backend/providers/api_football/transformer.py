"""Normalize API-Football fixtures without borrowing IDs from another provider."""

import re
from datetime import datetime
from decimal import Decimal
from config.competitions import get_competition
from config.core_constants import MatchStatus, MatchOutcome, MatchEventType, MatchPeriod
from elt_pipeline.transform.data_structures import (
    ParsedLeague, ParsedSeason, ParsedTeam, ParsedStadium, ParsedPlayer, ParsedMatch,
    ParsedMatchBundle, ParsedMatchEvent, ParsedLineup, ParsedMatchTeamStats,
)
from providers.base.abstract_provider import AbstractDataTransformer
from providers.base.components import ComponentStatus

STATUSES = {"NS": MatchStatus.SCHEDULED, "TBD": MatchStatus.POSTPONED,
    "PST": MatchStatus.POSTPONED, "CANC": MatchStatus.CANCELLED,
    "ABD": MatchStatus.ABANDONED, "AWD": MatchStatus.CANCELLED, "WO": MatchStatus.CANCELLED,
    "FT": MatchStatus.FINISHED,
    **{key: MatchStatus.IN_PROGRESS for key in ("1H", "HT", "2H", "LIVE", "SUSP", "INT")}}


class ApiFootballTransformer(AbstractDataTransformer):
    provider_name = "api_football"

    def transform(self, raw_bundle):
        profile = getattr(self, "competition", None) or get_competition()
        item = raw_bundle.detail
        fixture, league = item["fixture"], item["league"]
        if fixture["status"]["short"] not in STATUSES:
            raise ValueError("Extra time, penalties or unsupported match status cannot label a league H/D/A dataset")
        name, start, end = profile.season(str(league["season"]))
        season = ParsedSeason(league["season"], name, start, end, ParsedLeague(league["id"], league["name"], league["country"]))
        teams = {side: ParsedTeam(item["teams"][side]["id"], item["teams"][side]["name"], logo_url=item["teams"][side].get("logo"))
                 for side in ("home", "away")}
        by_id = {team.external_id: team for team in teams.values()}
        status = STATUSES[fixture["status"]["short"]]
        goals = item.get("score", {}).get("fulltime", {})
        home, away = goals.get("home"), goals.get("away")
        outcome = None
        if status == MatchStatus.FINISHED:
            if type(home) is not int or type(away) is not int or min(home, away) < 0:
                raise ValueError("Finished fixture must include a valid regulation-time score")
            outcome = MatchOutcome.H if home > away else MatchOutcome.A if away > home else MatchOutcome.D
        else:
            home = away = None
        venue = fixture.get("venue") or {}
        stadium = ParsedStadium(venue["id"], venue["name"], venue.get("city")) if venue.get("id") and venue.get("name") else None
        round_match = re.search(r"(\d+)$", league.get("round", ""))
        halftime = item.get("score", {}).get("halftime", {})
        match = ParsedMatch(fixture["id"], season, datetime.fromisoformat(fixture["date"].replace("Z", "+00:00")),
            round_match[1] if round_match else None, teams["home"], teams["away"], stadium, None,
            status, outcome, home, away, halftime.get("home"), halftime.get("away"))
        bundle = ParsedMatchBundle(match, component_status=dict(raw_bundle.component_status), raw_payload={
            "detail": raw_bundle.detail, "incidents": raw_bundle.incidents,
            "lineups": raw_bundle.lineups, "statistics": raw_bundle.statistics})
        for event in raw_bundle.incidents.get("response", []):
            kind, detail = event["type"], event.get("detail", "")
            mapped = {"Goal": MatchEventType.GOAL, "subst": MatchEventType.SUBSTITUTION,
                "Var": MatchEventType.VAR_DECISION}.get(kind)
            if kind == "Card":
                mapped = MatchEventType.RED_CARD if detail == "Red Card" else MatchEventType.YELLOW_CARD
            if kind == "Goal":
                mapped = {"Own Goal": MatchEventType.OWN_GOAL, "Missed Penalty": MatchEventType.MISSED_PENALTY,
                          "Penalty": MatchEventType.PENALTY_GOAL}.get(detail, mapped)
            if mapped is None:
                raise ValueError(f"Unsupported event type: {kind}")
            minute = event["time"]["elapsed"]
            player = event.get("player") or {}
            bundle.events.append(ParsedMatchEvent(minute, mapped, by_id[event["team"]["id"]],
                ParsedPlayer(player["id"], player["name"]) if player.get("id") and player.get("name") else None,
                None, MatchPeriod.FIRST_HALF if minute <= 45 else MatchPeriod.SECOND_HALF,
                description=detail, raw_event_data=event))
        lineups = raw_bundle.lineups.get("response", []) if bundle.component_status.get("lineups") == ComponentStatus.COMPLETE else []
        for lineup in lineups:
            team = by_id[lineup["team"]["id"]]
            for starter, key in ((True, "startXI"), (False, "substitutes")):
                for entry in lineup.get(key, []):
                    player = entry["player"]
                    bundle.lineups.append(ParsedLineup(ParsedPlayer(player["id"], player["name"]), team,
                        starter, player.get("number"), False, player.get("pos")))
        fields = {"Total Shots": "total_shots", "Shots on Goal": "shots_on_target", "Shots off Goal": "shots_off_target",
            "Blocked Shots": "blocked_shots", "Fouls": "fouls_committed", "Corner Kicks": "corners",
            "Offsides": "offsides", "Yellow Cards": "yellow_cards", "Red Cards": "red_cards", "Goalkeeper Saves": "saves"}
        statistics = raw_bundle.statistics.get("response", []) if bundle.component_status.get("team_stats") == ComponentStatus.COMPLETE else []
        for team_stats in statistics:
            values = {}
            for stat in team_stats["statistics"]:
                value = stat.get("value")
                if value is None:
                    continue
                if stat["type"] == "Ball Possession":
                    values["possession_percentage"] = Decimal(str(value).rstrip("%"))
                elif stat["type"] in fields:
                    values[fields[stat["type"]]] = int(value)
            bundle.team_stats.append(ParsedMatchTeamStats(by_id[team_stats["team"]["id"]], **values))
        return bundle
