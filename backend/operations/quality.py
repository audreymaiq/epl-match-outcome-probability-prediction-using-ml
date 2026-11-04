"""Competition-scoped data quality report, shared by CLI and automation."""

from sqlalchemy import text
from config.competitions import get_competition, competition_id
from utils.db_connector import DatabaseConnector


def check_data(league, seasons=None):
    competition = get_competition(league)
    with DatabaseConnector.session_scope() as session:
        league_id = competition_id(session, competition)
        rows = session.execute(text('''SELECT s.name, m.id, m.home_team_id, m.away_team_id,
                m.match_datetime, m.status::text AS status, m.outcome::text AS outcome,
                m.home_goals, m.away_goals, m.match_week
            FROM "Matches" m JOIN "Seasons" s ON s.id=m.season_id WHERE s.league_id=:id'''), {"id": league_id}).mappings().all()
    requested = {competition.season(name)[0] for name in seasons} if seasons else None
    if requested:
        rows = [row for row in rows if row["name"] in requested]
    errors = []
    if not rows:
        errors.append({"reason": "No matches in the requested scope"})
    available = {row["name"] for row in rows}
    if requested and requested-available:
        errors.append({"reason": "Requested seasons missing", "seasons": sorted(requested-available)})
    summary = {}
    for row in rows:
        summary.setdefault(row["name"], {"matches": 0, "finished": 0, "scheduled": 0})
        summary[row["name"]]["matches"] += 1
        if row["status"] == "FINISHED":
            summary[row["name"]]["finished"] += 1
            h, a = row["home_goals"], row["away_goals"]
            expected = "H" if h is not None and a is not None and h > a else "A" if h is not None and a is not None and a > h else "D"
            if h is None or a is None or min(h, a) < 0 or row["outcome"] != expected:
                errors.append({"match_id": row["id"], "reason": "Invalid score or outcome"})
        if row["status"] == "SCHEDULED":
            summary[row["name"]]["scheduled"] += 1
        if row["home_team_id"] == row["away_team_id"]:
            errors.append({"match_id": row["id"], "reason": "Identical teams"})
        if row["match_week"] is not None:
            try:
                valid = 1 <= int(row["match_week"]) <= competition.rounds
            except (ValueError, TypeError):
                valid = False
            if not valid:
                errors.append({"match_id": row["id"], "reason": "Invalid competition round"})
    return {"passed": not errors, "league": competition.slug, "seasons": summary,
            "errors": errors, "coverage_note": "Counts describe provider observations; full-season completeness requires a source catalogue with an expected fixture count."}
