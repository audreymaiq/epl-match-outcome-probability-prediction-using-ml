# feature_pipeline/computers/referee_computer.py
"""
Referee Bias Stats Computer.

Aggregates per-referee statistics and writes to RefereeStats table.
Key features for ML:
  - cards_per_game (yellow, red)
  - home_win_rate (does this ref favour home teams?)
  - draw_rate
  - fouls_per_game
  - penalty_rate (inferred from events if available)

Time-safe: only counts matches before current match.
"""

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from feature_pipeline.computers.base_computer import AbstractFeatureComputer

logger = logging.getLogger(__name__)


class RefereeComputer(AbstractFeatureComputer):

    @property
    def name(self) -> str:
        return "RefereeStats"

    def compute(self, session: Session, season_name: Optional[str] = None) -> int:
        logger.info("Computing RefereeStats (cumulative, all-time).")

        sql = """
        WITH ref_match_history AS (
            SELECT
                anchor.id        AS anchor_match_id,
                anchor.referee_id,
                COUNT(hist.id)   AS games_officiated,
                ROUND(AVG(
                    COALESCE(
                        (SELECT SUM(e.id::int * 0 + 1)
                         FROM "MatchEvents" e
                         WHERE e.match_id = hist.id
                           AND e.event_type = 'yellow card'), 0
                    )
                )::NUMERIC, 3)   AS avg_yellow_cards,
                ROUND(AVG(
                    COALESCE(
                        (SELECT SUM(e.id::int * 0 + 1)
                         FROM "MatchEvents" e
                         WHERE e.match_id = hist.id
                           AND e.event_type = 'red card'), 0
                    )
                )::NUMERIC, 3)   AS avg_red_cards,
                ROUND(AVG(
                    CASE WHEN hist.outcome = 'H' THEN 1.0 ELSE 0.0 END
                )::NUMERIC, 3)   AS home_win_rate,
                ROUND(AVG(
                    CASE WHEN hist.outcome = 'D' THEN 1.0 ELSE 0.0 END
                )::NUMERIC, 3)   AS draw_rate
            FROM "Matches" anchor
            JOIN "Matches" hist ON
                hist.referee_id = anchor.referee_id
                AND hist.match_datetime < anchor.match_datetime
                AND hist.status = 'FINISHED'
            WHERE anchor.referee_id IS NOT NULL
              AND anchor.status = 'FINISHED'
            GROUP BY anchor.id, anchor.referee_id
        )
        INSERT INTO "RefereeStats" (
            match_id, referee_id,
            games_officiated,
            avg_yellow_cards, avg_red_cards,
            home_win_rate, draw_rate,
            computed_at
        )
        SELECT
            r.anchor_match_id,
            r.referee_id,
            r.games_officiated,
            r.avg_yellow_cards, r.avg_red_cards,
            r.home_win_rate, r.draw_rate,
            NOW()
        FROM ref_match_history r
        ON CONFLICT (match_id, referee_id) DO UPDATE SET
            games_officiated  = EXCLUDED.games_officiated,
            avg_yellow_cards  = EXCLUDED.avg_yellow_cards,
            avg_red_cards     = EXCLUDED.avg_red_cards,
            home_win_rate     = EXCLUDED.home_win_rate,
            draw_rate         = EXCLUDED.draw_rate,
            computed_at       = NOW()
        """

        result = session.execute(text(sql))
        rows = result.rowcount
        logger.info("RefereeStats: upserted %d rows.", rows)
        return rows

