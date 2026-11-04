# api/services/team_service.py
"""Team Service - DB queries for team data."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from api.schemas.team import (
    TeamSchema, TeamDetailSchema, TeamSeasonStats, TeamFormEntry,
    TeamFormResponse, TeamStatsResponse, TeamSeasonSplitStats, SeasonBrief,
    H2HResponse,
)
from api.schemas.match import MatchListItem, TeamBriefSchema
from api.exceptions import NotFoundException

logger = logging.getLogger(__name__)


class TeamService:

    def __init__(self, session: Session, competition=None):
        from config.competitions import get_competition
        self.competition = competition or get_competition()
        self._db = session

    def _execute(self, statement, parameters=None):
        return self._db.execute(statement, {"league_slug": self.competition.slug, **(parameters or {})})

    # ── Public API ────────────────────────────────────────────────────────────

    def list_teams(
        self,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[TeamSchema], int]:
        filters = ['''EXISTS (SELECT 1 FROM "Matches" sm JOIN "Seasons" ss ON ss.id=sm.season_id
            JOIN "Leagues" sl ON sl.id=ss.league_id WHERE sl.slug=:league_slug
            AND (sm.home_team_id=t.id OR sm.away_team_id=t.id))''']
        params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
        if search:
            filters.append("LOWER(t.name) LIKE :search")
            params["search"] = f"%{search.lower()}%"

        where = ("WHERE " + " AND ".join(filters)) if filters else ""

        sql = f"""
            SELECT
                t.id, t.name, t.short_name, t.logo_url, t.established_year,
                s.name AS stadium_name, s.capacity AS stadium_capacity
            FROM "Teams" t
            LEFT JOIN "Stadiums" s ON s.id = t.stadium_id
            {where}
            ORDER BY t.name ASC
            LIMIT :limit OFFSET :offset
        """
        count_sql = f'SELECT COUNT(*) FROM "Teams" t {where}'

        rows = self._execute(text(sql), params).fetchall()
        total = self._execute(
            text(count_sql),
            {k: v for k, v in params.items() if k not in ("limit", "offset")},
        ).scalar()

        items = [
            TeamSchema(
                id=r.id, name=r.name, short_name=r.short_name,
                logo_url=r.logo_url, established_year=r.established_year,
                stadium_name=r.stadium_name, stadium_capacity=r.stadium_capacity,
            )
            for r in rows
        ]
        return items, int(total or 0)

    def get_team_detail(self, team_id: int, season_name: Optional[str] = None) -> TeamDetailSchema:
        """Get team with current season stats and last-5 form."""
        sql = """
            SELECT
                t.id, t.name, t.short_name, t.logo_url, t.established_year,
                s.name AS stadium_name, s.capacity
            FROM "Teams" t
            LEFT JOIN "Stadiums" s ON s.id = t.stadium_id
            WHERE t.id = :tid AND EXISTS (
                SELECT 1 FROM "Matches" m JOIN "Seasons" season ON season.id=m.season_id
                JOIN "Leagues" league ON league.id=season.league_id
                WHERE league.slug=:league_slug AND (m.home_team_id=t.id OR m.away_team_id=t.id)
            )
        """
        row = self._execute(text(sql), {"tid": team_id}).fetchone()
        if not row:
            raise NotFoundException("Team", team_id)

        season_stats = self._get_season_stats(team_id, season_name)
        form = self._get_last_5_form(team_id)

        return TeamDetailSchema(
            id=row.id, name=row.name, short_name=row.short_name,
            logo_url=row.logo_url, established_year=row.established_year,
            stadium_name=row.stadium_name,
            current_season_stats=season_stats,
            last_5_form=form,
        )

    def get_team_form(self, team_id: int) -> TeamFormResponse:
        """Get team's last 5 form for the dedicated /form endpoint."""
        brief = self._get_team_brief(team_id)
        entries = self._get_last_5_form(team_id)
        form_string = "".join(e.outcome for e in entries)
        points_total = sum(e.points for e in entries)
        return TeamFormResponse(
            team=brief,
            form=entries,
            form_string=form_string,
            points_last_5=points_total,
        )

    def get_team_stats(self, team_id: int, season_name: Optional[str] = None) -> TeamStatsResponse:
        """Get team's season stats with overall/home/away splits."""
        brief = self._get_team_brief(team_id)

        overall = self._get_split_stats(team_id, season_name, location=None)
        home = self._get_split_stats(team_id, season_name, location="home")
        away = self._get_split_stats(team_id, season_name, location="away")

        season_brief = None
        if overall:
            season_brief = SeasonBrief(name=overall.pop("_season_name", "Unknown"))

        def _build_split(data: Optional[dict]) -> TeamSeasonSplitStats:
            if not data:
                return TeamSeasonSplitStats(
                    played=0, wins=0, draws=0, losses=0,
                    goals_scored=0, goals_conceded=0, goal_difference=0,
                    points=0, win_rate=0.0, avg_goals_scored=0.0, avg_goals_conceded=0.0,
                )
            data.pop("_season_name", None)
            return TeamSeasonSplitStats(**data)

        return TeamStatsResponse(
            team=brief,
            season=season_brief,
            overall=_build_split(overall),
            home=_build_split(home),
            away=_build_split(away),
        )

    def get_h2h(self, home_team_id: int, away_team_id: int) -> H2HResponse:
        """Get all-time head-to-head stats + 5 most recent meetings."""
        # Both teams must participate in the requested competition.
        for tid in (home_team_id, away_team_id):
            self._get_team_brief(tid)

        h2h_sql = """
            SELECT
                COUNT(*)                                             AS total,
                SUM(CASE WHEN (home_team_id=:hid AND outcome='H') OR (away_team_id=:hid AND outcome='A') THEN 1 ELSE 0 END) AS hw,
                SUM(CASE WHEN outcome = 'D' THEN 1 ELSE 0 END)     AS draws,
                SUM(CASE WHEN (home_team_id=:aid AND outcome='H') OR (away_team_id=:aid AND outcome='A') THEN 1 ELSE 0 END) AS aw,
                ROUND(AVG(CASE WHEN home_team_id=:hid THEN home_goals ELSE away_goals END)::NUMERIC, 2) AS avg_hg,
                ROUND(AVG(CASE WHEN home_team_id=:aid THEN home_goals ELSE away_goals END)::NUMERIC, 2) AS avg_ag,
                ROUND(AVG(CASE WHEN (home_goals + away_goals) > 2 THEN 1.0 ELSE 0.0 END)::NUMERIC, 3) AS o25,
                ROUND(AVG(CASE WHEN home_goals > 0 AND away_goals > 0 THEN 1.0 ELSE 0.0 END)::NUMERIC, 3) AS btts
            FROM "Matches" scope_m JOIN "Seasons" scope_s ON scope_s.id=scope_m.season_id JOIN "Leagues" scope_l ON scope_l.id=scope_s.league_id AND scope_l.slug=:league_slug
            WHERE ((home_team_id=:hid AND away_team_id=:aid) OR (home_team_id=:aid AND away_team_id=:hid))
              AND status = 'FINISHED'
        """
        h2h = self._execute(text(h2h_sql), {"hid": home_team_id, "aid": away_team_id}).fetchone()

        recent_sql = """
            SELECT
                m.id, s.name AS season_name,
                to_char(m.match_datetime, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS match_datetime, m.match_week,
                m.status, m.outcome, m.home_goals, m.away_goals,
                ht.id AS ht_id, ht.name AS ht_name, ht.logo_url AS ht_logo,
                at.id AS at_id, at.name AS at_name, at.logo_url AS at_logo
            FROM "Matches" m JOIN "Seasons" scope_s ON scope_s.id=m.season_id JOIN "Leagues" scope_l ON scope_l.id=scope_s.league_id AND scope_l.slug=:league_slug
            JOIN "Seasons" s ON s.id = m.season_id
            JOIN "Teams" ht  ON ht.id = m.home_team_id
            JOIN "Teams" at  ON at.id = m.away_team_id
            WHERE ((m.home_team_id=:hid AND m.away_team_id=:aid) OR (m.home_team_id=:aid AND m.away_team_id=:hid))
              AND m.status = 'FINISHED'
            ORDER BY m.match_datetime DESC
            LIMIT 5
        """
        recent_rows = self._execute(text(recent_sql), {"hid": home_team_id, "aid": away_team_id}).fetchall()

        home_name = self._execute(text('SELECT name, logo_url FROM "Teams" WHERE id = :id'), {"id": home_team_id}).fetchone()
        away_name = self._execute(text('SELECT name, logo_url FROM "Teams" WHERE id = :id'), {"id": away_team_id}).fetchone()

        return H2HResponse(
            home_team=TeamBriefSchema(id=home_team_id, name=home_name.name, logo_url=home_name.logo_url),
            away_team=TeamBriefSchema(id=away_team_id, name=away_name.name, logo_url=away_name.logo_url),
            total_meetings=int(h2h.total or 0),
            home_wins=int(h2h.hw or 0),
            draws=int(h2h.draws or 0),
            away_wins=int(h2h.aw or 0),
            avg_home_goals=float(h2h.avg_hg or 0),
            avg_away_goals=float(h2h.avg_ag or 0),
            over_2_5_rate=float(h2h.o25 or 0),
            btts_rate=float(h2h.btts or 0),
            recent_matches=[
                MatchListItem(
                    id=r.id, season_name=r.season_name,
                    match_datetime=r.match_datetime, match_week=r.match_week,
                    home_team=TeamBriefSchema(id=r.ht_id, name=r.ht_name, logo_url=r.ht_logo),
                    away_team=TeamBriefSchema(id=r.at_id, name=r.at_name, logo_url=r.at_logo),
                    status=r.status, outcome=r.outcome,
                    home_goals=r.home_goals, away_goals=r.away_goals,
                )
                for r in recent_rows
            ],
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_team_brief(self, team_id: int) -> TeamBriefSchema:
        """Fetch a minimal team record for embedding in responses."""
        row = self._execute(
            text('''SELECT t.id, t.name, t.short_name, t.logo_url FROM "Teams" t
                WHERE t.id=:tid AND EXISTS (
                    SELECT 1 FROM "Matches" m JOIN "Seasons" s ON s.id=m.season_id
                    JOIN "Leagues" l ON l.id=s.league_id WHERE l.slug=:league_slug
                    AND (m.home_team_id=t.id OR m.away_team_id=t.id))'''),
            {"tid": team_id},
        ).fetchone()
        if not row:
            raise NotFoundException("Team", team_id)
        return TeamBriefSchema(id=row.id, name=row.name, short_name=row.short_name, logo_url=row.logo_url)

    def _get_season_stats(self, team_id: int, season_name: Optional[str]) -> Optional[TeamSeasonStats]:
        """Get aggregated season stats. Defaults to latest season if not specified."""
        sql = """
            SELECT
                s.name AS season_name,
                COUNT(*)              AS mp,
                SUM(CASE WHEN (m.home_team_id = :tid AND m.outcome = 'H') OR (m.away_team_id = :tid AND m.outcome = 'A') THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN m.outcome = 'D' THEN 1 ELSE 0 END) AS draws,
                SUM(CASE WHEN (m.home_team_id = :tid AND m.outcome = 'A') OR (m.away_team_id = :tid AND m.outcome = 'H') THEN 1 ELSE 0 END) AS losses,
                SUM(CASE WHEN m.home_team_id = :tid THEN m.home_goals ELSE m.away_goals END) AS gf,
                SUM(CASE WHEN m.home_team_id = :tid THEN m.away_goals ELSE m.home_goals END) AS ga,
                SUM(CASE WHEN (m.home_team_id = :tid AND m.outcome = 'H') OR (m.away_team_id = :tid AND m.outcome = 'A') THEN 3
                         WHEN m.outcome = 'D' THEN 1 ELSE 0 END) AS pts,
                SUM(CASE WHEN (m.home_team_id = :tid AND m.away_goals = 0) OR (m.away_team_id = :tid AND m.home_goals = 0) THEN 1 ELSE 0 END) AS cs
            FROM "Matches" m JOIN "Seasons" scope_s ON scope_s.id=m.season_id JOIN "Leagues" scope_l ON scope_l.id=scope_s.league_id AND scope_l.slug=:league_slug
            JOIN "Seasons" s ON s.id = m.season_id
            WHERE (m.home_team_id = :tid OR m.away_team_id = :tid)
              AND m.status = 'FINISHED'
              AND (:season IS NULL OR s.name = :season)
            GROUP BY s.name
            ORDER BY MAX(s.start_year) DESC
            LIMIT 1
        """
        row = self._execute(text(sql), {"tid": team_id, "season": season_name}).fetchone()
        if not row or not row.mp:
            return None

        pts = int(row.pts or 0)
        mp = int(row.mp or 1)
        return TeamSeasonStats(
            season_name=row.season_name,
            matches_played=mp,
            wins=int(row.wins or 0),
            draws=int(row.draws or 0),
            losses=int(row.losses or 0),
            goals_scored=int(row.gf or 0),
            goals_conceded=int(row.ga or 0),
            points=pts,
            ppg=round(pts / mp, 3),
            clean_sheets=int(row.cs or 0),
        )

    def _get_last_5_form(self, team_id: int) -> List[TeamFormEntry]:
        sql = """
            SELECT
                m.id,
                to_char(m.match_datetime, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS match_date,
                CASE WHEN m.home_team_id = :tid THEN at.name ELSE ht.name END AS opponent,
                CASE WHEN m.home_team_id = :tid THEN 'Home' ELSE 'Away' END AS location,
                CASE WHEN m.home_team_id = :tid THEN m.home_goals ELSE m.away_goals END AS gf,
                CASE WHEN m.home_team_id = :tid THEN m.away_goals ELSE m.home_goals END AS ga,
                m.outcome
            FROM "Matches" m JOIN "Seasons" scope_s ON scope_s.id=m.season_id JOIN "Leagues" scope_l ON scope_l.id=scope_s.league_id AND scope_l.slug=:league_slug
            JOIN "Teams" ht ON ht.id = m.home_team_id
            JOIN "Teams" at ON at.id = m.away_team_id
            WHERE (m.home_team_id = :tid OR m.away_team_id = :tid)
              AND m.status = 'FINISHED'
            ORDER BY m.match_datetime DESC
            LIMIT 5
        """
        rows = self._execute(text(sql), {"tid": team_id}).fetchall()

        entries = []
        for r in rows:
            is_home = r.location == "Home"
            if r.outcome == "D":
                outcome = "D"
                points = 1
            elif (is_home and r.outcome == "H") or (not is_home and r.outcome == "A"):
                outcome = "W"
                points = 3
            else:
                outcome = "L"
                points = 0

            entries.append(TeamFormEntry(
                match_id=r.id,
                match_date=r.match_date,
                opponent_name=r.opponent,
                location=r.location,
                goals_scored=r.gf or 0,
                goals_conceded=r.ga or 0,
                outcome=outcome,
                points=points,
            ))
        return entries

    def _get_split_stats(
        self,
        team_id: int,
        season_name: Optional[str],
        location: Optional[str],  # None=overall, "home", "away"
    ) -> Optional[dict]:
        """Get stats for a specific location split."""
        location_filter = ""
        if location == "home":
            location_filter = "AND m.home_team_id = :tid"
        elif location == "away":
            location_filter = "AND m.away_team_id = :tid"
        else:
            location_filter = "AND (m.home_team_id = :tid OR m.away_team_id = :tid)"

        sql = f"""
            SELECT
                s.name AS season_name,
                COUNT(*) AS mp,
                SUM(CASE WHEN (m.home_team_id = :tid AND m.outcome = 'H') OR (m.away_team_id = :tid AND m.outcome = 'A') THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN m.outcome = 'D' THEN 1 ELSE 0 END) AS draws,
                SUM(CASE WHEN (m.home_team_id = :tid AND m.outcome = 'A') OR (m.away_team_id = :tid AND m.outcome = 'H') THEN 1 ELSE 0 END) AS losses,
                SUM(CASE WHEN m.home_team_id = :tid THEN m.home_goals ELSE m.away_goals END) AS gf,
                SUM(CASE WHEN m.home_team_id = :tid THEN m.away_goals ELSE m.home_goals END) AS ga,
                SUM(CASE WHEN (m.home_team_id = :tid AND m.outcome = 'H') OR (m.away_team_id = :tid AND m.outcome = 'A') THEN 3
                         WHEN m.outcome = 'D' THEN 1 ELSE 0 END) AS pts
            FROM "Matches" m JOIN "Seasons" scope_s ON scope_s.id=m.season_id JOIN "Leagues" scope_l ON scope_l.id=scope_s.league_id AND scope_l.slug=:league_slug
            JOIN "Seasons" s ON s.id = m.season_id
            WHERE m.status = 'FINISHED'
              {location_filter}
              AND (:season IS NULL OR s.name = :season)
            GROUP BY s.name
            ORDER BY MAX(s.start_year) DESC
            LIMIT 1
        """
        row = self._execute(text(sql), {"tid": team_id, "season": season_name}).fetchone()
        if not row or not row.mp:
            return None

        mp = int(row.mp or 1)
        wins = int(row.wins or 0)
        gf = int(row.gf or 0)
        ga = int(row.ga or 0)
        pts = int(row.pts or 0)

        return {
            "_season_name": row.season_name,
            "played": mp,
            "wins": wins,
            "draws": int(row.draws or 0),
            "losses": int(row.losses or 0),
            "goals_scored": gf,
            "goals_conceded": ga,
            "goal_difference": gf - ga,
            "points": pts,
            "win_rate": round(wins / mp, 3) if mp > 0 else 0.0,
            "avg_goals_scored": round(gf / mp, 2) if mp > 0 else 0.0,
            "avg_goals_conceded": round(ga / mp, 2) if mp > 0 else 0.0,
        }
