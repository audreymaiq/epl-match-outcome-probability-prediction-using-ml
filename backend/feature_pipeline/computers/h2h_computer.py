# feature_pipeline/computers/h2h_computer.py
"""
Head-to-Head Stats Computer.

Aggregates historical H2H results between every pair of teams
and writes to HeadToHeadStats table.

IMPORTANT: H2H considers BOTH directions (A@home vs B, AND B@home vs A)
as meetings between the same pair. The stats are always stored from
the perspective of the ANCHOR match's home/away assignment.

Stats computed (all matches BEFORE the current match - no leakage):
  - total meetings, home_wins, draws, away_wins (from perspective of canonical pair)
  - home/away goals averages
  - btts_rate (both teams to score %)
  - over_2_5_rate (over 2.5 goals %)

Time-safe: hist.match_datetime < anchor.match_datetime (strict pre-match).
"""

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from feature_pipeline.computers.base_computer import AbstractFeatureComputer

logger = logging.getLogger(__name__)


class H2HComputer(AbstractFeatureComputer):

    @property
    def name(self) -> str:
        return "HeadToHeadStats"

    def compute(self, session: Session, season_name: Optional[str] = None) -> int:
        logger.info("Computing HeadToHeadStats (all-time, both directions).")

        # For each anchor match (hid vs aid), find ALL historical meetings
        # between those two teams in BOTH directions:
        #   - hist matches where (home=hid, away=aid) → direct mapping
        #   - hist matches where (home=aid, away=hid) → reversed mapping
        # Stats are aggregated from the anchor match's perspective:
        #   "home_wins" = times hid beat aid (regardless of venue in history)
        sql = """
        WITH h2h_agg AS (
            SELECT
                anchor.id                                     AS anchor_match_id,
                anchor.home_team_id                           AS anchor_home_id,
                anchor.away_team_id                           AS anchor_away_id,
                COUNT(*)                                      AS total_meetings,
                -- Home wins = anchor's home team won (as home OR as away in prior meetings)
                SUM(CASE
                    WHEN hist.home_team_id = anchor.home_team_id AND hist.outcome = 'H' THEN 1
                    WHEN hist.away_team_id = anchor.home_team_id AND hist.outcome = 'A' THEN 1
                    ELSE 0
                END)                                          AS home_wins,
                SUM(CASE WHEN hist.outcome = 'D' THEN 1 ELSE 0 END) AS draws,
                -- Away wins = anchor's away team won
                SUM(CASE
                    WHEN hist.home_team_id = anchor.away_team_id AND hist.outcome = 'H' THEN 1
                    WHEN hist.away_team_id = anchor.away_team_id AND hist.outcome = 'A' THEN 1
                    ELSE 0
                END)                                          AS away_wins,
                -- Average goals from perspective of anchor's home team
                ROUND(AVG(CASE
                    WHEN hist.home_team_id = anchor.home_team_id THEN hist.home_goals
                    ELSE hist.away_goals
                END)::NUMERIC, 3)                             AS avg_home_goals,
                ROUND(AVG(CASE
                    WHEN hist.home_team_id = anchor.home_team_id THEN hist.away_goals
                    ELSE hist.home_goals
                END)::NUMERIC, 3)                             AS avg_away_goals,
                ROUND(AVG(CASE WHEN (hist.home_goals + hist.away_goals) > 2
                    THEN 1.0 ELSE 0.0 END)::NUMERIC, 3)      AS over_2_5_rate,
                ROUND(AVG(CASE WHEN hist.home_goals > 0 AND hist.away_goals > 0
                    THEN 1.0 ELSE 0.0 END)::NUMERIC, 3)      AS btts_rate
            FROM "Matches" anchor
            JOIN "Matches" hist ON
                -- Both directions: hist involves the same two teams as anchor
                (
                    (hist.home_team_id = anchor.home_team_id AND hist.away_team_id = anchor.away_team_id)
                    OR
                    (hist.home_team_id = anchor.away_team_id AND hist.away_team_id = anchor.home_team_id)
                )
                AND hist.match_datetime < anchor.match_datetime
                AND hist.status = 'FINISHED'
                AND hist.home_goals IS NOT NULL
            WHERE anchor.status = 'FINISHED'
              AND anchor.home_goals IS NOT NULL
            GROUP BY anchor.id, anchor.home_team_id, anchor.away_team_id
        )
        INSERT INTO "HeadToHeadStats" (
            match_id,
            home_team_id, away_team_id,
            total_meetings, home_wins, draws, away_wins,
            avg_home_goals, avg_away_goals,
            over_2_5_rate, btts_rate,
            computed_at
        )
        SELECT
            a.anchor_match_id,
            a.anchor_home_id,
            a.anchor_away_id,
            a.total_meetings,
            a.home_wins, a.draws, a.away_wins,
            a.avg_home_goals, a.avg_away_goals,
            a.over_2_5_rate, a.btts_rate,
            NOW()
        FROM h2h_agg a
        ON CONFLICT (match_id) DO UPDATE SET
            total_meetings  = EXCLUDED.total_meetings,
            home_wins       = EXCLUDED.home_wins,
            draws           = EXCLUDED.draws,
            away_wins       = EXCLUDED.away_wins,
            avg_home_goals  = EXCLUDED.avg_home_goals,
            avg_away_goals  = EXCLUDED.avg_away_goals,
            over_2_5_rate   = EXCLUDED.over_2_5_rate,
            btts_rate       = EXCLUDED.btts_rate,
            computed_at     = NOW()
        """

        result = session.execute(text(sql))
        rows = result.rowcount
        logger.info("HeadToHeadStats: upserted %d rows.", rows)
        return rows
