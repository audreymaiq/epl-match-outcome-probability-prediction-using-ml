# ml/elo/elo_builder.py
"""
ELO Builder - Bootstraps ratings from all historical match data.

Responsibilities:
  1. Load all finished matches from DB in chronological order
  2. Apply season regression at the start of each new season
  3. Compute pre-match ELO (no leakage) and post-match ELO for each team
  4. Persist results to EloRatings table

Time-safety guarantee:
  - elo_before for match N uses only matches 1..N-1
  - elo_after for match N is persisted but NOT used as a feature for match N

Design:
  - Stateful (accumulates ratings per team) but deterministic
  - Rebuild from scratch each time (idempotent via UPSERT)
  - Accepts any EloCalculator config (testable, injectable)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from ml.elo.elo_calculator import EloCalculator, EloRecord, EloConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)


# Traditional EPL Top-6 teams (by name, normalized)
EPL_TOP_6 = frozenset([
    "Manchester City",
    "Manchester United",
    "Arsenal",
    "Liverpool",
    "Chelsea",
    "Tottenham Hotspur",
])


class EloBuilder:
    """
    Builds and persists ELO rating history from DB match records.

    Usage:
        builder = EloBuilder(session)
        builder.build_from_db()
        rows_saved = builder.save_to_db()
    """

    def __init__(
        self,
        session: Session,
        config: EloConfig = DEFAULT_CONFIG,
    ):
        self._db = session
        self._calc = EloCalculator(config)
        self._config = config

        # team_id → current ELO (updated as we process matches chronologically)
        self._ratings: Dict[int, float] = defaultdict(lambda: config.initial_elo)

        # All computed records, in order
        self._records: List[EloRecord] = []

        # Track which season each team last played in (for regression detection)
        self._team_last_season: Dict[int, str] = {}

        # Team name cache
        self._team_names: Dict[int, str] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def build_from_db(self) -> int:
        """
        Load all finished matches chronologically and compute ELO timeline.
        Returns number of match-team records computed.
        """
        matches = self._load_all_matches()
        logger.info("Building ELO from %d historical matches...", len(matches))

        self._team_names = self._load_team_names()
        self._records = []

        for match in matches:
            self._process_match(match)

        logger.info(
            "ELO build complete: %d records for %d teams.",
            len(self._records),
            len(self._ratings),
        )
        return len(self._records)

    def save_to_db(self) -> int:
        """
        Upsert all computed EloRecords into the EloRatings table.
        Safe to call multiple times (idempotent via ON CONFLICT DO UPDATE).
        Returns number of rows upserted.
        """
        if not self._records:
            logger.warning("No ELO records to save. Call build_from_db() first.")
            return 0

        upserted = 0
        batch_size = 500

        for i in range(0, len(self._records), batch_size):
            batch = self._records[i : i + batch_size]
            for rec in batch:
                self._db.execute(text("""
                    INSERT INTO "EloRatings" (
                        team_id, match_id, match_date,
                        elo_before, elo_after, k_factor, season
                    )
                    VALUES (
                        :team_id, :match_id, :match_date,
                        :elo_before, :elo_after, :k_factor, :season
                    )
                    ON CONFLICT (team_id, match_date, match_id) DO UPDATE SET
                        elo_before = EXCLUDED.elo_before,
                        elo_after  = EXCLUDED.elo_after,
                        k_factor   = EXCLUDED.k_factor,
                        updated_at = NOW()
                """), {
                    "team_id":   rec.team_id,
                    "match_id":  rec.match_id,
                    "match_date": rec.match_date,
                    "elo_before": rec.elo_before,
                    "elo_after":  rec.elo_after,
                    "k_factor":   rec.k_factor,
                    "season":     rec.season,
                })
                upserted += 1

            logger.debug("ELO save: batch %d-%d committed.", i, i + len(batch))

        logger.info("EloRatings: %d rows upserted.", upserted)
        return upserted

    def get_current_ratings(self) -> Dict[int, float]:
        """Return the latest ELO for each team (after all processed matches)."""
        return dict(self._ratings)

    def get_rating_at(self, team_id: int, before_date: date) -> float:
        """
        Get ELO for a team on a specific date (pre-match lookup).
        Returns initial ELO if no history.
        """
        relevant = [
            r for r in self._records
            if r.team_id == team_id and r.match_date < before_date
        ]
        if not relevant:
            return self._config.initial_elo
        latest = max(relevant, key=lambda r: (r.match_date, r.match_id or 0))
        return latest.elo_after

    # ── Private processing ────────────────────────────────────────────────────

    def _process_match(self, match: Dict) -> None:
        """
        Process one match:
          1. Apply season regression if new season
          2. Record pre-match ELO for BOTH teams
          3. Update ratings
          4. Record post-match ELO
        """
        home_id     = match["home_team_id"]
        away_id     = match["away_team_id"]
        match_id    = match["match_id"]
        match_date  = match["match_date"]
        home_goals  = match["home_goals"]
        away_goals  = match["away_goals"]
        season_name = match["season_name"]
        match_week  = match["match_week"]

        # 1. Season regression
        for team_id in (home_id, away_id):
            last_season = self._team_last_season.get(team_id)
            if last_season and last_season != season_name:
                old = self._ratings[team_id]
                self._ratings[team_id] = self._calc.season_regression(old)
                logger.debug(
                    "Season regression: team %d | %s → %s | ELO %.0f → %.0f",
                    team_id, last_season, season_name, old, self._ratings[team_id],
                )
            self._team_last_season[team_id] = season_name

        # 2. Snapshot pre-match ELO
        home_elo_before = round(self._ratings[home_id], 2)
        away_elo_before = round(self._ratings[away_id], 2)

        # 3. Determine match importance flags
        try:
            week = int(match_week) if match_week else 20
        except (ValueError, TypeError):
            week = 20

        home_name = self._team_names.get(home_id, "")
        away_name = self._team_names.get(away_id, "")
        is_top6 = home_name in EPL_TOP_6 and away_name in EPL_TOP_6

        # 4. Update ratings
        new_home_elo, new_away_elo = self._calc.update(
            home_elo=home_elo_before,
            away_elo=away_elo_before,
            home_goals=home_goals,
            away_goals=away_goals,
            match_week=week,
            is_top6_clash=is_top6,
        )

        self._ratings[home_id] = new_home_elo
        self._ratings[away_id] = new_away_elo

        # 5. Compute effective K-factor (for record)
        k_effective = abs(new_home_elo - home_elo_before) / max(
            abs(1.0 if home_goals > away_goals else 0.5 if home_goals == away_goals else 0.0
                - self._calc.expected_score(home_elo_before + self._calc._cfg.home_advantage, away_elo_before)),
            1e-6
        )

        # 6. Append records
        self._records.append(EloRecord(
            team_id=home_id,
            match_id=match_id,
            match_date=match_date,
            elo_before=home_elo_before,
            elo_after=round(new_home_elo, 2),
            k_factor=round(min(k_effective, self._calc._cfg.k_max), 2),
            season=season_name,
        ))
        self._records.append(EloRecord(
            team_id=away_id,
            match_id=match_id,
            match_date=match_date,
            elo_before=away_elo_before,
            elo_after=round(new_away_elo, 2),
            k_factor=round(min(k_effective, self._calc._cfg.k_max), 2),
            season=season_name,
        ))

    def _load_all_matches(self) -> List[Dict]:
        """
        Load all finished matches in strict chronological order.
        Only loads matches with valid score data.
        """
        sql = """
            SELECT
                m.id              AS match_id,
                m.home_team_id,
                m.away_team_id,
                DATE(m.match_datetime) AS match_date,
                m.home_goals,
                m.away_goals,
                m.match_week,
                s.name            AS season_name
            FROM "Matches" m
            JOIN "Seasons" s ON s.id = m.season_id
            WHERE m.status = 'FINISHED'
              AND m.home_goals IS NOT NULL
              AND m.away_goals IS NOT NULL
            ORDER BY m.match_datetime ASC, m.id ASC
        """
        rows = self._db.execute(text(sql)).fetchall()
        return [
            {
                "match_id":     r.match_id,
                "home_team_id": r.home_team_id,
                "away_team_id": r.away_team_id,
                "match_date":   r.match_date,
                "home_goals":   int(r.home_goals),
                "away_goals":   int(r.away_goals),
                "match_week":   r.match_week,
                "season_name":  r.season_name,
            }
            for r in rows
        ]

    def _load_team_names(self) -> Dict[int, str]:
        rows = self._db.execute(text('SELECT id, name FROM "Teams"')).fetchall()
        return {r.id: r.name for r in rows}
