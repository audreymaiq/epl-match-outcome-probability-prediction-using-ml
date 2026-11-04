# api/services/match_service.py
"""
Match Service - DB queries for match data.

All queries are raw SQL for performance transparency.
No ORM magic, no N+1 queries.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from api.schemas.match import MatchListItem, MatchDetail, TeamBriefSchema, StadiumSchema, RefereeSchema
from api.exceptions import NotFoundException

logger = logging.getLogger(__name__)


class MatchService:

    def __init__(self, session: Session, competition=None):
        from config.competitions import get_competition
        self.competition = competition or get_competition()
        self._db = session

    def _execute(self, statement, parameters=None):
        return self._db.execute(statement, {"league_slug": self.competition.slug, **(parameters or {})})

    def list_matches(
        self,
        season_name: Optional[str] = None,
        status: Optional[str] = None,
        team_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[MatchListItem], int]:
        """
        Return paginated match list with optional filters.
        Returns (items, total_count).
        """
        filters = []
        params: dict = {}

        if season_name:
            filters.append("s.name = :season")
            params["season"] = season_name
        if status:
            filters.append("m.status = :status")
            params["status"] = status.upper()
            if status.upper() == "SCHEDULED":
                filters.append("m.match_datetime > (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')")
        if team_id is not None:
            filters.append("(m.home_team_id = :team_id OR m.away_team_id = :team_id)")
            params["team_id"] = team_id

        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size

        sql = f"""
            SELECT
                m.id, s.name AS season_name,
                to_char(m.match_datetime, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS match_datetime, m.match_week,
                m.status, m.outcome,
                m.home_goals, m.away_goals,
                ht.id AS ht_id, ht.name AS ht_name, ht.logo_url AS ht_logo,
                at.id AS at_id, at.name AS at_name, at.logo_url AS at_logo
            FROM "Matches" m JOIN "Seasons" scope_s ON scope_s.id=m.season_id JOIN "Leagues" scope_l ON scope_l.id=scope_s.league_id AND scope_l.slug=:league_slug
            JOIN "Seasons" s   ON s.id = m.season_id
            JOIN "Teams" ht    ON ht.id = m.home_team_id
            JOIN "Teams" at    ON at.id = m.away_team_id
            {where}
            ORDER BY m.match_datetime {('ASC' if status and status.upper() == 'SCHEDULED' else 'DESC')}
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"""
            SELECT COUNT(*) FROM "Matches" m JOIN "Seasons" scope_s ON scope_s.id=m.season_id JOIN "Leagues" scope_l ON scope_l.id=scope_s.league_id AND scope_l.slug=:league_slug
            JOIN "Seasons" s ON s.id = m.season_id
            {where}
        """

        rows = self._execute(text(sql), params).fetchall()
        total = self._execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

        items = [
            MatchListItem(
                id=r.id,
                season_name=r.season_name,
                match_datetime=r.match_datetime,
                match_week=r.match_week,
                home_team=TeamBriefSchema(id=r.ht_id, name=r.ht_name, logo_url=r.ht_logo),
                away_team=TeamBriefSchema(id=r.at_id, name=r.at_name, logo_url=r.at_logo),
                status=r.status,
                outcome=r.outcome,
                home_goals=r.home_goals,
                away_goals=r.away_goals,
            )
            for r in rows
        ]
        return items, int(total or 0)

    def get_match_detail(self, match_id: int) -> MatchDetail:
        """Fetch full match detail including team stats."""
        sql = """
            SELECT
                m.id, s.name AS season_name,
                to_char(m.match_datetime, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS match_datetime, m.match_week,
                m.status, m.outcome,
                m.home_goals, m.away_goals,
                m.half_time_home_goals, m.half_time_away_goals,
                m.attendance,
                ht.id AS ht_id, ht.name AS ht_name, ht.logo_url AS ht_logo,
                at.id AS at_id, at.name AS at_name, at.logo_url AS at_logo,
                st.id AS st_id, st.name AS st_name, st.city AS st_city, st.capacity AS st_cap,
                r.id AS ref_id, r.name AS ref_name, r.country AS ref_country,
                -- Team stats
                hts.possession_percentage AS h_poss,
                ats.possession_percentage AS a_poss,
                hts.total_shots AS h_shots,
                ats.total_shots AS a_shots,
                hts.shots_on_target AS h_sot,
                ats.shots_on_target AS a_sot,
                hts.corners AS h_corners,
                ats.corners AS a_corners
            FROM "Matches" m JOIN "Seasons" scope_s ON scope_s.id=m.season_id JOIN "Leagues" scope_l ON scope_l.id=scope_s.league_id AND scope_l.slug=:league_slug
            JOIN "Seasons" s    ON s.id = m.season_id
            JOIN "Teams" ht     ON ht.id = m.home_team_id
            JOIN "Teams" at     ON at.id = m.away_team_id
            LEFT JOIN "Stadiums" st   ON st.id = m.stadium_id
            LEFT JOIN "Referees" r    ON r.id = m.referee_id
            LEFT JOIN "MatchTeamStats" hts ON hts.match_id = m.id AND hts.team_id = m.home_team_id
            LEFT JOIN "MatchTeamStats" ats ON ats.match_id = m.id AND ats.team_id = m.away_team_id
            WHERE m.id = :match_id
        """
        row = self._execute(text(sql), {"match_id": match_id}).fetchone()
        if not row:
            raise NotFoundException("Match", match_id)

        return MatchDetail(
            id=row.id,
            season_name=row.season_name,
            match_datetime=row.match_datetime,
            match_week=row.match_week,
            home_team=TeamBriefSchema(id=row.ht_id, name=row.ht_name, logo_url=row.ht_logo),
            away_team=TeamBriefSchema(id=row.at_id, name=row.at_name, logo_url=row.at_logo),
            status=row.status,
            outcome=row.outcome,
            home_goals=row.home_goals,
            away_goals=row.away_goals,
            half_time_home_goals=row.half_time_home_goals,
            half_time_away_goals=row.half_time_away_goals,
            stadium=StadiumSchema(id=row.st_id, name=row.st_name, city=row.st_city, capacity=row.st_cap) if row.st_id else None,
            referee=RefereeSchema(id=row.ref_id, name=row.ref_name, country=row.ref_country) if row.ref_id else None,
            attendance=row.attendance,
            home_possession=float(row.h_poss) if row.h_poss is not None else None,
            away_possession=float(row.a_poss) if row.a_poss is not None else None,
            home_shots=row.h_shots,
            away_shots=row.a_shots,
            home_shots_on_target=row.h_sot,
            away_shots_on_target=row.a_sot,
            home_corners=row.h_corners,
            away_corners=row.a_corners,
        )
