"""
Team Season Location Stats Computer.

Aggregates cumulative season statistics split by location (Home/Away/Overall).
Writes to TeamSeasonLocationStats table.

Stats:
  - matches_played, wins, draws, losses
  - goals_scored, goals_conceded
  - points, ppg (points per game)
  - xG (if available from MatchTeamStats)
  - clean_sheets, failed_to_score

Time-safe: only counts matches strictly BEFORE the current match date.
"""

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ml.features.batch.computers.base_computer import AbstractFeatureComputer

logger = logging.getLogger(__name__)


class SeasonComputer(AbstractFeatureComputer):

    @property
    def name(self) -> str:
        return "TeamSeasonLocationStats"

    def compute(self, session: Session, season_name: Optional[str] = None, *, league_id=None, competition=None, config=None) -> int:
        logger.info(
            "Computing TeamSeasonLocationStats%s...",
            f" for season {season_name}" if season_name else " (all seasons)",
        )

        season_filter = ""
        params: dict = {"league_id": league_id}
        if season_name:
            season_filter = "AND s.name = :season_name"
            params["season_name"] = season_name

        sql = f"""
        WITH match_results AS (
            SELECT
                m.id            AS match_id,
                m.match_datetime,
                m.season_id,
                m.home_team_id  AS team_id,
                'Home'          AS location,
                m.home_goals    AS scored,
                m.away_goals    AS conceded,
                CASE WHEN m.outcome = 'H' THEN 3
                     WHEN m.outcome = 'D' THEN 1
                     ELSE 0 END AS points,
                CASE WHEN m.outcome = 'H' THEN 1 ELSE 0 END AS win,
                CASE WHEN m.outcome = 'D' THEN 1 ELSE 0 END AS draw,
                CASE WHEN m.outcome = 'A' THEN 1 ELSE 0 END AS loss,
                CASE WHEN m.away_goals = 0 THEN 1 ELSE 0 END AS clean_sheet,
                CASE WHEN m.home_goals = 0 THEN 1 ELSE 0 END AS failed_to_score
            FROM "Matches" m JOIN "Seasons" scope_s ON scope_s.id=m.season_id AND scope_s.league_id=:league_id
            JOIN "Seasons" s ON s.id = m.season_id
            WHERE m.status = 'FINISHED' AND m.home_goals IS NOT NULL
              {season_filter}

            UNION ALL

            SELECT
                m.id, m.match_datetime, m.season_id,
                m.away_team_id, 'Away',
                m.away_goals, m.home_goals,
                CASE WHEN m.outcome = 'A' THEN 3
                     WHEN m.outcome = 'D' THEN 1
                     ELSE 0 END,
                CASE WHEN m.outcome = 'A' THEN 1 ELSE 0 END,
                CASE WHEN m.outcome = 'D' THEN 1 ELSE 0 END,
                CASE WHEN m.outcome = 'H' THEN 1 ELSE 0 END,
                CASE WHEN m.home_goals = 0 THEN 1 ELSE 0 END,
                CASE WHEN m.away_goals = 0 THEN 1 ELSE 0 END
            FROM "Matches" m JOIN "Seasons" scope_s ON scope_s.id=m.season_id AND scope_s.league_id=:league_id
            JOIN "Seasons" s ON s.id = m.season_id
            WHERE m.status = 'FINISHED' AND m.away_goals IS NOT NULL
              {season_filter}
        ),
        season_agg AS (
            SELECT
                anchor.match_id,
                hist.team_id,
                hist.season_id,
                hist.location,
                COUNT(*)              AS matches_played,
                SUM(hist.win)         AS wins,
                SUM(hist.draw)        AS draws,
                SUM(hist.loss)        AS losses,
                SUM(hist.scored)      AS goals_scored,
                SUM(hist.conceded)    AS goals_conceded,
                SUM(hist.points)      AS points,
                ROUND(AVG(hist.points)::NUMERIC, 4)    AS ppg,
                SUM(hist.clean_sheet)       AS clean_sheets,
                SUM(hist.failed_to_score)   AS failed_to_score
            FROM match_results anchor
            JOIN match_results hist ON
                hist.team_id   = anchor.team_id
                AND hist.season_id = anchor.season_id
                AND hist.location  = anchor.location
                AND hist.season_id IN (SELECT id FROM "Seasons" WHERE league_id=:league_id)
                AND hist.match_datetime < anchor.match_datetime
            GROUP BY anchor.match_id, hist.team_id, hist.season_id, hist.location
        )
        INSERT INTO "TeamSeasonLocationStats" (
            match_id, team_id, season_id, location,
            matches_played, wins, draws, losses,
            goals_scored, goals_conceded, points, ppg,
            clean_sheets, failed_to_score, computed_at
        )
        SELECT
            s.match_id, s.team_id, s.season_id, s.location::"LocationType",
            s.matches_played, s.wins, s.draws, s.losses,
            s.goals_scored, s.goals_conceded, s.points, s.ppg,
            s.clean_sheets, s.failed_to_score, NOW()
        FROM season_agg s
        ON CONFLICT (match_id, team_id, location) DO UPDATE SET
            matches_played  = EXCLUDED.matches_played,
            wins            = EXCLUDED.wins,
            draws           = EXCLUDED.draws,
            losses          = EXCLUDED.losses,
            goals_scored    = EXCLUDED.goals_scored,
            goals_conceded  = EXCLUDED.goals_conceded,
            points          = EXCLUDED.points,
            ppg             = EXCLUDED.ppg,
            clean_sheets    = EXCLUDED.clean_sheets,
            failed_to_score = EXCLUDED.failed_to_score,
            computed_at     = NOW()
        """

        result = session.execute(text(sql), params)
        rows = result.rowcount
        logger.info("TeamSeasonLocationStats: upserted %d rows.", rows)
        return rows

