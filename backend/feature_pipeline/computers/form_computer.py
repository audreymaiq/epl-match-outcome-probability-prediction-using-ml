# feature_pipeline/computers/form_computer.py
"""
Team Form Stats Computer.

Aggregates rolling form metrics per team (last 5, last 10 matches)
and writes to TeamFormStats table.

Stats computed:
  - wins / draws / losses (last 5 and last 10)
  - goals scored / conceded averages
  - points per game
  - home/away breakdown
  - clean sheets
  - momentum (weighted by recency)

Time-safe: all aggregation is BEFORE match_datetime - no leakage.

ARCHITECTURE:
  This computer runs in the feature_pipeline (batch ETL layer).
  FeatureExtractor computes model features directly from Matches for both
  training and inference. This table is a separate unweighted summary for
  reporting and must not be substituted for the model's weighted features.
"""

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from feature_pipeline.computers.base_computer import AbstractFeatureComputer

logger = logging.getLogger(__name__)


class FormComputer(AbstractFeatureComputer):

    @property
    def name(self) -> str:
        return "TeamFormStats"

    def compute(self, session: Session, season_name: Optional[str] = None) -> int:
        """
        Compute rolling form for every (team, match) pair.

        Strategy:
          1. Normalise all finished matches into a per-team perspective (match_results CTE).
          2. For each (team_id, match_id) anchor, find the N most recent prior matches
             for that team STRICTLY BEFORE the anchor match's datetime.
          3. Aggregate last-5 and last-10 windows.
          4. Upsert into TeamFormStats table.

        Critical: The window function MUST use a LATERAL subquery or a proper
        self-join with the anchor's match_datetime, NOT the mr2.match_datetime
        (which would create a circular reference).
        """
        logger.info(
            "Computing TeamFormStats%s...",
            f" for season {season_name}" if season_name else " (all seasons)",
        )

        anchor_season_filter = ""
        params: dict = {}
        if season_name:
            anchor_season_filter = "AND anchor_s.name = :season_name"
            params["season_name"] = season_name

        # Step 1: Build normalised match_results (per-team perspective)
        # Step 2: For each anchor match, use LATERAL to find prior matches
        #         for the SAME team, ordered by date DESC, limited to 10.
        # Step 3: Aggregate into last-5 and last-10 windows.
        sql = f"""
        WITH match_results AS (
            -- Normalise every finished match into per-team perspective
            SELECT
                m.id            AS match_id,
                m.match_datetime,
                m.season_id,
                m.home_team_id  AS team_id,
                m.home_goals    AS goals_scored,
                m.away_goals    AS goals_conceded,
                CASE
                    WHEN m.outcome = 'H' THEN 3
                    WHEN m.outcome = 'D' THEN 1
                    ELSE 0
                END             AS points,
                CASE WHEN m.outcome = 'H' THEN 1 ELSE 0 END AS is_win,
                CASE WHEN m.outcome = 'D' THEN 1 ELSE 0 END AS is_draw,
                CASE WHEN m.outcome = 'A' THEN 1 ELSE 0 END AS is_loss,
                CASE WHEN m.away_goals = 0 THEN 1 ELSE 0 END AS clean_sheet
            FROM "Matches" m
            WHERE m.status = 'FINISHED'
              AND m.home_goals IS NOT NULL

            UNION ALL

            SELECT
                m.id,
                m.match_datetime,
                m.season_id,
                m.away_team_id,
                m.away_goals,
                m.home_goals,
                CASE
                    WHEN m.outcome = 'A' THEN 3
                    WHEN m.outcome = 'D' THEN 1
                    ELSE 0
                END,
                CASE WHEN m.outcome = 'A' THEN 1 ELSE 0 END,
                CASE WHEN m.outcome = 'D' THEN 1 ELSE 0 END,
                CASE WHEN m.outcome = 'H' THEN 1 ELSE 0 END,
                CASE WHEN m.home_goals = 0 THEN 1 ELSE 0 END
            FROM "Matches" m
            WHERE m.status = 'FINISHED'
              AND m.away_goals IS NOT NULL
        ),
        -- All anchors: every (match_id, team_id) that we need form stats for
        anchors AS (
            SELECT DISTINCT
                m.id            AS match_id,
                m.match_datetime AS anchor_dt,
                m.season_id,
                t.team_id
            FROM "Matches" m
            JOIN "Seasons" anchor_s ON anchor_s.id = m.season_id
            CROSS JOIN LATERAL (
                VALUES (m.home_team_id), (m.away_team_id)
            ) AS t(team_id)
            WHERE m.status = 'FINISHED'
              AND m.home_goals IS NOT NULL
              {anchor_season_filter}
        ),
        -- For each anchor, rank prior matches (same team, before anchor_dt)
        ranked_prior AS (
            SELECT
                a.match_id      AS anchor_match_id,
                a.team_id,
                a.season_id,
                mr.goals_scored,
                mr.goals_conceded,
                mr.points,
                mr.is_win,
                mr.is_draw,
                mr.is_loss,
                mr.clean_sheet,
                ROW_NUMBER() OVER (
                    PARTITION BY a.match_id, a.team_id
                    ORDER BY mr.match_datetime DESC, mr.match_id DESC
                ) AS rn
            FROM anchors a
            JOIN match_results mr ON
                mr.team_id = a.team_id
                AND mr.match_datetime < a.anchor_dt
        ),
        form_5 AS (
            SELECT
                anchor_match_id AS match_id,
                team_id,
                season_id,
                COUNT(*)                          AS form5_matches_played,
                SUM(is_win)                       AS form5_wins,
                SUM(is_draw)                      AS form5_draws,
                SUM(is_loss)                      AS form5_losses,
                ROUND(AVG(goals_scored)::NUMERIC, 3)   AS form5_avg_scored,
                ROUND(AVG(goals_conceded)::NUMERIC, 3) AS form5_avg_conceded,
                ROUND(AVG(points)::NUMERIC, 3)         AS form5_ppg,
                SUM(clean_sheet)                  AS form5_clean_sheets,
                SUM(goals_scored)                 AS form5_goals_scored,
                SUM(goals_conceded)               AS form5_goals_conceded
            FROM ranked_prior
            WHERE rn <= 5
            GROUP BY anchor_match_id, team_id, season_id
        ),
        form_10 AS (
            SELECT
                anchor_match_id AS match_id,
                team_id,
                SUM(is_win)  AS form10_wins,
                SUM(is_draw) AS form10_draws,
                SUM(is_loss) AS form10_losses,
                ROUND(AVG(goals_scored)::NUMERIC, 3)   AS form10_avg_scored,
                ROUND(AVG(goals_conceded)::NUMERIC, 3) AS form10_avg_conceded,
                ROUND(AVG(points)::NUMERIC, 3)         AS form10_ppg
            FROM ranked_prior
            WHERE rn <= 10
            GROUP BY anchor_match_id, team_id
        )
        INSERT INTO "TeamFormStats" (
            match_id, team_id, season_id,
            form5_matches_played,
            form5_wins, form5_draws, form5_losses,
            form5_goals_scored, form5_goals_conceded,
            form5_avg_scored, form5_avg_conceded, form5_ppg, form5_clean_sheets,
            form10_wins, form10_draws, form10_losses,
            form10_avg_scored, form10_avg_conceded, form10_ppg,
            computed_at
        )
        SELECT
            f5.match_id,
            f5.team_id,
            f5.season_id,
            f5.form5_matches_played,
            f5.form5_wins, f5.form5_draws, f5.form5_losses,
            f5.form5_goals_scored, f5.form5_goals_conceded,
            f5.form5_avg_scored, f5.form5_avg_conceded, f5.form5_ppg, f5.form5_clean_sheets,
            COALESCE(f10.form10_wins, 0),
            COALESCE(f10.form10_draws, 0),
            COALESCE(f10.form10_losses, 0),
            COALESCE(f10.form10_avg_scored, f5.form5_avg_scored),
            COALESCE(f10.form10_avg_conceded, f5.form5_avg_conceded),
            COALESCE(f10.form10_ppg, f5.form5_ppg),
            NOW()
        FROM form_5 f5
        LEFT JOIN form_10 f10 ON f10.match_id = f5.match_id AND f10.team_id = f5.team_id
        ON CONFLICT (match_id, team_id) DO UPDATE SET
            form5_matches_played  = EXCLUDED.form5_matches_played,
            form5_wins            = EXCLUDED.form5_wins,
            form5_draws           = EXCLUDED.form5_draws,
            form5_losses          = EXCLUDED.form5_losses,
            form5_goals_scored    = EXCLUDED.form5_goals_scored,
            form5_goals_conceded  = EXCLUDED.form5_goals_conceded,
            form5_avg_scored      = EXCLUDED.form5_avg_scored,
            form5_avg_conceded    = EXCLUDED.form5_avg_conceded,
            form5_ppg             = EXCLUDED.form5_ppg,
            form5_clean_sheets    = EXCLUDED.form5_clean_sheets,
            form10_wins           = EXCLUDED.form10_wins,
            form10_draws          = EXCLUDED.form10_draws,
            form10_losses         = EXCLUDED.form10_losses,
            form10_avg_scored     = EXCLUDED.form10_avg_scored,
            form10_avg_conceded   = EXCLUDED.form10_avg_conceded,
            form10_ppg            = EXCLUDED.form10_ppg,
            computed_at           = NOW()
        """

        result = session.execute(text(sql), params)
        rows = result.rowcount
        logger.info("TeamFormStats: upserted %d rows.", rows)
        return rows
