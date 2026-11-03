# ml/features/feature_extractor.py
"""Extract match features for training and pre match inference."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple, List

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from ml.elo.elo_calculator import EloCalculator, EloConfig
from ml.config import MLConfig, load_ml_config

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """
    Builds a flat feature vector for one match from aggregated DB data.

    Usage:
        extractor = FeatureExtractor(session)
        df = extractor.extract_for_match(match_id)        # → DataFrame (1 row)
        df = extractor.extract_all_finished_matches()      # → DataFrame (N rows)
    """

    def __init__(self, session: Session, config: Optional[MLConfig] = None):
        self._db = session
        self._config = config or load_ml_config()
        self._defaults = self._config.features.defaults
        self._elo_config = EloConfig(**self._config.elo)
        self._derbies = frozenset(frozenset(pair) for pair in self._config.features.derbies)
        self._top_teams = frozenset(self._config.features.top_teams)

    # ── Public entry points ───────────────────────────────────────────────────

    def extract_for_match(self, match_id: int) -> Optional[pd.DataFrame]:
        """Extract features for a single known match (by internal DB id)."""
        meta = self._fetch_match_meta(match_id)
        if meta is None:
            logger.warning("Match %d not found in DB.", match_id)
            return None
        row = self._build_feature_row(meta)
        return pd.DataFrame([row])

    def extract_for_fixture(
        self,
        home_team_id: int,
        away_team_id: int,
        match_datetime: str,
        season_name: str,
        match_week: int,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Extract features for a future fixture not yet in DB.
        Used by PredictionService for real-time inference.
        """
        if not season_name:
            raise ValueError("season_name is required for a custom fixture.")
        if not 1 <= match_week <= 38:
            raise ValueError("match_week must be between 1 and 38.")
        dt = datetime.fromisoformat(match_datetime)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        season = self._db.execute(text("""
            SELECT s.id, s.name
            FROM "Seasons" s
            WHERE s.name = :season_name
            LIMIT 1
        """), {"season_name": season_name}).fetchone()
        if season is None:
            raise ValueError(f"Unknown season: {season_name}")
        home_team_name = self._get_team_name(home_team_id)
        away_team_name = self._get_team_name(away_team_id)
        if not home_team_name or not away_team_name:
            raise ValueError("Both team IDs must exist in the database.")
        season_teams = self._db.execute(text("""
            SELECT COUNT(DISTINCT team_id) AS team_count
            FROM (
                SELECT home_team_id AS team_id
                FROM "Matches"
                WHERE season_id = :season_id
                  AND home_team_id IN (:home_id, :away_id)
                UNION
                SELECT away_team_id AS team_id
                FROM "Matches"
                WHERE season_id = :season_id
                  AND away_team_id IN (:home_id, :away_id)
            ) AS participating_teams
        """), {
            "season_id": season.id,
            "home_id": home_team_id,
            "away_id": away_team_id,
        }).fetchone()
        if not season_teams or season_teams.team_count != 2:
            raise ValueError("Both teams must have participated in the requested season.")
        meta = {
            "match_id": None,
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "match_datetime": dt,
            "match_week": str(match_week),
            "season_id": season.id,
            "season_name": season.name,
            "referee_id": None,
            "home_team_name": home_team_name,
            "away_team_name": away_team_name,
            "outcome": None,
        }
        row = self._build_feature_row(meta)
        return pd.DataFrame([row]), meta

    def extract_all_finished_matches(
        self,
        season_name: Optional[str] = None,
        min_match_week: int = 0,
    ) -> pd.DataFrame:
        """
        Build feature matrix for ALL finished matches.
        Used for model training.

        Args:
            season_name:     Limit to one season (None = all).
            min_match_week:  Optional lower bound for matchweek filtering.
                             Early-season matches are included by default; their
                             features use only prior-season history and fallbacks.

        Returns:
            DataFrame with features + 'outcome' column (H/D/A).
        """
        matches = self._fetch_all_finished_matches(season_name, min_match_week)
        logger.info("Building features for %d matches...", len(matches))

        rows = []
        for i, meta in enumerate(matches):
            try:
                row = self._build_feature_row(meta)
                rows.append(row)
            except Exception as exc:
                logger.warning("Feature extraction failed for match %d: %s", meta.get("match_id"), exc)

            if (i + 1) % 100 == 0:
                logger.info("  Processed %d / %d matches...", i + 1, len(matches))

        df = pd.DataFrame(rows)
        logger.info("Feature matrix built: %d rows × %d cols", len(df), len(df.columns))
        return df

    def get_match_meta(self, match_id: int) -> Dict[str, Any]:
        return self._fetch_match_meta(match_id) or {}

    # ── Core feature builder ──────────────────────────────────────────────────

    def _build_feature_row(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrates all feature groups for one match.
        Each group returns a flat dict of feature_name → value.
        Final row = union of all group dicts.
        """
        match_id = meta.get("match_id")
        home_id  = meta["home_team_id"]
        away_id  = meta["away_team_id"]
        dt       = meta["match_datetime"]
        season_id = meta.get("season_id")
        referee_id = meta.get("referee_id")

        row: Dict[str, Any] = {
            "match_id":   match_id,
            "outcome":    meta.get("outcome"),    # target variable (None for future)
        }

        # ── TIER 1: ELO ──────────────────────────────────────────────────────
        elo_feats = self._features_elo(home_id, away_id, dt, meta.get("season_name"))
        row.update(elo_feats)

        # ── TIER 1: Rolling Form ─────────────────────────────────────────────
        home_form = self._features_form(home_id, dt, prefix="home", location_filter=None)
        away_form = self._features_form(away_id, dt, prefix="away", location_filter=None)
        row.update(home_form)
        row.update(away_form)
        row.update(self._features_form(home_id, dt, prefix="home_home", location_filter="Home"))
        row.update(self._features_form(away_id, dt, prefix="away_away", location_filter="Away"))

        # ── TIER 1: Season cumulative stats ──────────────────────────────────
        home_season = self._features_season(home_id, dt, season_id, prefix="home", location="Overall")
        away_season = self._features_season(away_id, dt, season_id, prefix="away", location="Overall")
        row.update(home_season)
        row.update(away_season)
        row.update(self._features_season(home_id, dt, season_id, prefix="home_home", location="Home"))
        row.update(self._features_season(away_id, dt, season_id, prefix="away_away", location="Away"))

        # ── TIER 1: Head-to-head (BOTH directions) ──────────────────────────
        row.update(self._features_h2h(home_id, away_id, dt))

        # ── TIER 2: Attack/Defense strength (Dixon-Coles style) ──────────────
        row.update(self._features_attack_defense(home_id, away_id, dt, season_id))

        # ── TIER 2: Squad availability ────────────────────────────────────────
        row.update(self._features_squad(home_id, away_id, dt))

        # ── TIER 2: Referee tendencies ────────────────────────────────────────
        row.update(self._features_referee(referee_id, dt))

        # ── TIER 2: Rest/fatigue ──────────────────────────────────────────────
        row.update(self._features_rest(home_id, away_id, dt))

        # ── TIER 3: Streaks ───────────────────────────────────────────────────
        row.update(self._features_streaks(home_id, away_id, dt))

        # ── TIER 3: Derby / rivalry ───────────────────────────────────────────
        row.update(self._features_derby(home_id, away_id))

        # ── TIER 3: Season stage ──────────────────────────────────────────────
        row.update(self._features_season_stage(meta.get("match_week"), dt))

        # ── TIER 3: Team-specific home advantage ─────────────────────────────
        row.update(self._features_home_advantage(home_id, away_id, dt))

        # ── TIER 4: European competition fatigue ─────────────────────────────
        row.update(self._features_european_fatigue(home_id, away_id, dt))

        # ── DERIVED: Cross-features (critical for accuracy) ──────────────────
        row.update(self._derived_features(row, home_form, away_form, home_season, away_season, elo_feats))

        return row

    # ── TIER 1: ELO features ─────────────────────────────────────────────────

    def _features_elo(
        self, home_id: int, away_id: int, dt: datetime, season_name: Optional[str]
    ) -> Dict[str, Any]:
        """
        Pre-match ELO ratings - fetched from EloRatings table.
        Uses the configured prior for teams with no history.
        """
        def rating_before_match(team_id: int) -> float:
            latest = self._get_latest_elo(team_id, dt)
            if latest is None:
                return self._defaults["elo"]
            rating, previous_season = latest
            if season_name and previous_season != season_name:
                return EloCalculator(self._elo_config).season_regression(rating)
            return rating

        home_elo = rating_before_match(home_id)
        away_elo = rating_before_match(away_id)
        elo_diff = home_elo - away_elo

        # Logistic win probability (ELO standard)
        elo_win_prob_home = 1.0 / (1.0 + 10.0 ** (-elo_diff / self._elo_config.rating_scale))
        # Apply the configured home advantage in Elo points.
        elo_win_prob_home_adj = 1.0 / (
            1.0 + 10.0 ** (-(elo_diff + self._elo_config.home_advantage) / self._elo_config.rating_scale)
        )

        return {
            "home_elo_before":       round(home_elo, 2),
            "away_elo_before":       round(away_elo, 2),
            "elo_diff":              round(elo_diff, 2),
            "elo_win_prob_home":     round(elo_win_prob_home, 4),
            "elo_win_prob_home_adj": round(elo_win_prob_home_adj, 4),
        }

    def _get_latest_elo(self, team_id: int, before_dt: datetime) -> Optional[Tuple[float, str]]:
        """Get the most recent ELO rating for a team before the given datetime."""
        row = self._db.execute(text("""
            SELECT e.elo_after, e.season
            FROM "EloRatings" e
            JOIN "Matches" m ON m.id = e.match_id
            WHERE e.team_id = :tid
              AND m.match_datetime < :dt
            ORDER BY m.match_datetime DESC, m.id DESC
            LIMIT 1
        """), {"tid": team_id, "dt": before_dt}).fetchone()
        return (float(row.elo_after), row.season) if row else None

    # ── TIER 1: Rolling form ─────────────────────────────────────────────────

    def _features_form(
        self,
        team_id: int,
        before_dt: datetime,
        prefix: str,
        location_filter: Optional[str] = None,  # "Home" | "Away" | None (all)
        n_last: int = 10,
    ) -> Dict[str, Any]:
        """
        Compute rolling form statistics for last 5 and last 10 matches.
        Weighted by recency using the configured exponential decay.
        """
        loc_cond = ""
        params: Dict[str, Any] = {"tid": team_id, "dt": before_dt, "n": n_last}

        if location_filter == "Home":
            loc_cond = "AND m.home_team_id = :tid"
        elif location_filter == "Away":
            loc_cond = "AND m.away_team_id = :tid"

        sql = f"""
            SELECT
                m.match_datetime,
                CASE
                    WHEN m.home_team_id = :tid THEN m.home_goals ELSE m.away_goals
                END AS scored,
                CASE
                    WHEN m.home_team_id = :tid THEN m.away_goals ELSE m.home_goals
                END AS conceded,
                CASE
                    WHEN m.home_team_id = :tid AND m.outcome = 'H' THEN 'W'
                    WHEN m.away_team_id = :tid AND m.outcome = 'A' THEN 'W'
                    WHEN m.outcome = 'D' THEN 'D'
                    ELSE 'L'
                END AS result
            FROM "Matches" m
            WHERE (m.home_team_id = :tid OR m.away_team_id = :tid)
              AND m.status = 'FINISHED'
              AND m.match_datetime < :dt
              AND m.home_goals IS NOT NULL
              {loc_cond}
            ORDER BY m.match_datetime DESC
            LIMIT :n
        """
        rows = self._db.execute(text(sql), params).fetchall()

        if not rows:
            return self._form_defaults(prefix)

        results = [r.result for r in rows]
        scored   = [r.scored   or 0 for r in rows]
        conceded = [r.conceded or 0 for r in rows]
        # Most recent match has weight 1; earlier matches decay by age.
        weights = [self._config.features.form_decay ** i for i in range(len(rows))]

        def weighted_avg(values, w):
            return sum(v * wt for v, wt in zip(values, w)) / sum(w) if w else 0

        def window(r, s, c, w, n):
            """Stats for last n matches."""
            r_ = r[:n]; s_ = s[:n]; c_ = c[:n]; w_ = w[:n]
            if not r_:
                return {}
            wins   = sum(1 for x in r_ if x == "W")
            draws  = sum(1 for x in r_ if x == "D")
            losses = sum(1 for x in r_ if x == "L")
            pts    = wins * 3 + draws
            cs     = sum(1 for x in c_ if x == 0)
            return {
                f"{prefix}_form{n}_matches_played": len(r_),
                f"{prefix}_form{n}_wins":           wins,
                f"{prefix}_form{n}_draws":          draws,
                f"{prefix}_form{n}_losses":         losses,
                f"{prefix}_form{n}_ppg":            round(pts / len(r_), 4),
                f"{prefix}_form{n}_avg_scored":     round(weighted_avg(s_, w_), 4),
                f"{prefix}_form{n}_avg_conceded":   round(weighted_avg(c_, w_), 4),
                f"{prefix}_form{n}_clean_sheets":   cs,
                f"{prefix}_form{n}_goal_diff":      round(sum(s_) - sum(c_), 2),
            }

        features = {}
        features.update(window(results, scored, conceded, weights, 5))
        features.update(window(results, scored, conceded, weights, 10))

        # Momentum score: points from last 5, linearly weighted newest=5pts
        momentum_weights = [5 - i for i in range(min(5, len(results)))]
        momentum = sum(
            (3 if r == "W" else 1 if r == "D" else 0) * w
            for r, w in zip(results[:5], momentum_weights)
        )
        features[f"{prefix}_momentum_score"] = momentum

        # Form consistency: std dev of points in last 5 (low = consistent)
        pts_list = [3 if r == "W" else 1 if r == "D" else 0 for r in results[:5]]
        features[f"{prefix}_form_consistency"] = round(float(np.std(pts_list)), 4) if len(pts_list) >= 3 else 0.0

        # Goals trend: avg scored in last 3 vs last 5 (>1 = improving attack)
        if len(scored) >= 5:
            recent3 = sum(scored[:3]) / 3.0
            last5avg = sum(scored[:5]) / 5.0
            features[f"{prefix}_goals_trend"] = round(recent3 / max(last5avg, 0.01), 4)
        else:
            features[f"{prefix}_goals_trend"] = 1.0

        return features

    def _form_defaults(self, prefix: str) -> Dict[str, Any]:
        d = {}
        for n in [5, 10]:
            d[f"{prefix}_form{n}_matches_played"] = 0
            d[f"{prefix}_form{n}_wins"]          = 0
            d[f"{prefix}_form{n}_draws"]         = 0
            d[f"{prefix}_form{n}_losses"]        = 0
            d[f"{prefix}_form{n}_ppg"]           = self._defaults["form5_ppg"]
            d[f"{prefix}_form{n}_avg_scored"]    = self._defaults["form5_avg_scored"]
            d[f"{prefix}_form{n}_avg_conceded"]  = self._defaults["form5_avg_conceded"]
            d[f"{prefix}_form{n}_clean_sheets"]  = 0
            d[f"{prefix}_form{n}_goal_diff"]     = 0.0
        d[f"{prefix}_momentum_score"] = 0
        d[f"{prefix}_form_consistency"] = 0.0
        d[f"{prefix}_goals_trend"] = 1.0
        return d

    # ── TIER 1: Season cumulative stats ──────────────────────────────────────

    def _features_season(
        self,
        team_id: int,
        before_dt: datetime,
        season_id: Optional[int],
        prefix: str,
        location: str = "Overall",   # "Overall" | "Home" | "Away"
    ) -> Dict[str, Any]:
        """
        Season-to-date statistics, split by location.
        Computed from raw Matches table to be always current.
        """
        if location == "Home":
            team_col = "home"
            loc_cond = "AND m.home_team_id = :tid"
            opp_goals_col = "away"
        elif location == "Away":
            team_col = "away"
            loc_cond = "AND m.away_team_id = :tid"
            opp_goals_col = "home"
        else:
            loc_cond = "AND (m.home_team_id = :tid OR m.away_team_id = :tid)"

        season_cond = "AND m.season_id = :sid" if season_id else ""
        params: Dict[str, Any] = {"tid": team_id, "dt": before_dt}
        if season_id:
            params["sid"] = season_id

        if location == "Overall":
            sql = f"""
                SELECT
                    COUNT(*) AS mp,
                    SUM(CASE WHEN m.home_team_id=:tid THEN m.home_goals ELSE m.away_goals END) AS gf,
                    SUM(CASE WHEN m.home_team_id=:tid THEN m.away_goals ELSE m.home_goals END) AS ga,
                    SUM(CASE
                        WHEN m.home_team_id=:tid AND m.outcome='H' THEN 3
                        WHEN m.away_team_id=:tid AND m.outcome='A' THEN 3
                        WHEN m.outcome='D' THEN 1
                        ELSE 0 END) AS pts,
                    SUM(CASE
                        WHEN m.home_team_id=:tid AND m.outcome='H' THEN 1
                        WHEN m.away_team_id=:tid AND m.outcome='A' THEN 1
                        ELSE 0 END) AS wins,
                    SUM(CASE WHEN m.outcome='D' THEN 1 ELSE 0 END) AS draws,
                    SUM(CASE
                        WHEN m.home_team_id=:tid AND m.outcome='A' THEN 1
                        WHEN m.away_team_id=:tid AND m.outcome='H' THEN 1
                        ELSE 0 END) AS losses,
                    SUM(CASE
                        WHEN m.home_team_id=:tid AND m.away_goals=0 THEN 1
                        WHEN m.away_team_id=:tid AND m.home_goals=0 THEN 1
                        ELSE 0 END) AS cs
                FROM "Matches" m
                WHERE (m.home_team_id=:tid OR m.away_team_id=:tid)
                  AND m.status = 'FINISHED'
                  AND m.match_datetime < :dt
                  AND m.home_goals IS NOT NULL
                  {season_cond}
            """
        else:
            outcome_win = "'H'" if location == "Home" else "'A'"
            outcome_loss = "'A'" if location == "Home" else "'H'"
            goals_for = f"m.{team_col}_goals"
            goals_ag  = f"m.{opp_goals_col}_goals"
            sql = f"""
                SELECT
                    COUNT(*) AS mp,
                    SUM({goals_for}) AS gf,
                    SUM({goals_ag}) AS ga,
                    SUM(CASE WHEN m.outcome={outcome_win} THEN 3 WHEN m.outcome='D' THEN 1 ELSE 0 END) AS pts,
                    SUM(CASE WHEN m.outcome={outcome_win} THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN m.outcome='D' THEN 1 ELSE 0 END) AS draws,
                    SUM(CASE WHEN m.outcome={outcome_loss} THEN 1 ELSE 0 END) AS losses,
                    SUM(CASE WHEN {goals_ag}=0 THEN 1 ELSE 0 END) AS cs
                FROM "Matches" m
                WHERE m.{team_col}_team_id=:tid
                  AND m.status = 'FINISHED'
                  AND m.match_datetime < :dt
                  AND m.home_goals IS NOT NULL
                  {season_cond}
            """

        row = self._db.execute(text(sql), params).fetchone()

        mp = int(row.mp or 0) if row else 0
        if mp < self._config.features.min_matches["season"]:
            suffix = f"_loc" if location != "Overall" else ""
            return {
                f"{prefix}_season{suffix}_mp":           mp,
                f"{prefix}_season{suffix}_ppg":          self._defaults["season_ppg"],
                f"{prefix}_season{suffix}_avg_scored":   self._defaults["season_avg_scored"],
                f"{prefix}_season{suffix}_avg_conceded": self._defaults["season_avg_conceded"],
                f"{prefix}_season{suffix}_win_rate":     self._defaults["h2h_home_win_rate"],
                f"{prefix}_season{suffix}_draw_rate":    self._defaults["h2h_draw_rate"],
                f"{prefix}_season{suffix}_loss_rate":    1 - self._defaults["h2h_home_win_rate"] - self._defaults["h2h_draw_rate"],
                f"{prefix}_season{suffix}_clean_sheets": 0,
                f"{prefix}_season{suffix}_gd":           0.0,
            }

        gf  = int(row.gf  or 0)
        ga  = int(row.ga  or 0)
        pts = int(row.pts or 0)
        suffix = "_loc" if location != "Overall" else ""

        return {
            f"{prefix}_season{suffix}_mp":           mp,
            f"{prefix}_season{suffix}_ppg":          round(pts / mp, 4),
            f"{prefix}_season{suffix}_avg_scored":   round(gf / mp, 4),
            f"{prefix}_season{suffix}_avg_conceded": round(ga / mp, 4),
            f"{prefix}_season{suffix}_win_rate":     round(int(row.wins or 0) / mp, 4),
            f"{prefix}_season{suffix}_draw_rate":    round(int(row.draws or 0) / mp, 4),
            f"{prefix}_season{suffix}_loss_rate":    round(int(row.losses or 0) / mp, 4),
            f"{prefix}_season{suffix}_clean_sheets": int(row.cs or 0),
            f"{prefix}_season{suffix}_gd":           round((gf - ga) / mp, 4),
        }

    # ── TIER 1: Head-to-head (BOTH directions) ──────────────────────────────

    def _features_h2h(
        self, home_id: int, away_id: int, before_dt: datetime
    ) -> Dict[str, Any]:
        """
        All-time H2H from BOTH directions: A@home vs B AND B@home vs A.
        Stats from perspective of anchor's home team.
        """
        # Query both directions
        sql = """
            SELECT
                m.home_team_id, m.away_team_id,
                m.home_goals, m.away_goals, m.outcome
            FROM "Matches" m
            WHERE (
                (m.home_team_id = :hid AND m.away_team_id = :aid)
                OR
                (m.home_team_id = :aid AND m.away_team_id = :hid)
            )
            AND m.status = 'FINISHED'
            AND m.match_datetime < :dt
            AND m.home_goals IS NOT NULL
            ORDER BY m.match_datetime DESC
        """
        rows = self._db.execute(text(sql), {"hid": home_id, "aid": away_id, "dt": before_dt}).fetchall()
        total = len(rows)

        if total < self._config.features.min_matches["h2h"]:
            return {
                "h2h_total_meetings":  total,
                "h2h_home_win_rate":   self._defaults["h2h_home_win_rate"],
                "h2h_draw_rate":       self._defaults["h2h_draw_rate"],
                "h2h_away_win_rate":   1 - self._defaults["h2h_home_win_rate"] - self._defaults["h2h_draw_rate"],
                "h2h_avg_home_goals":  self._defaults["form5_avg_scored"],
                "h2h_avg_away_goals":  self._defaults["form5_avg_scored"],
                "h2h_over_2_5_rate":   self._config.features.h2h_over_2_5_prior,
                "h2h_btts_rate":       self._config.features.h2h_btts_prior,
                "h2h_home_dominance":  0.0,
                "h2h_recent_trend":    0.0,
            }

        # Count from perspective of anchor's home team (home_id)
        hw = 0  # home_id wins
        aw = 0  # away_id wins
        dr = 0
        home_goals_total = 0  # goals scored by home_id
        away_goals_total = 0  # goals scored by away_id
        o25 = 0
        btts = 0

        for r in rows:
            if r.home_team_id == home_id:
                # Direct match: home_id was home
                hg, ag = r.home_goals, r.away_goals
                if r.outcome == "H":
                    hw += 1
                elif r.outcome == "A":
                    aw += 1
                else:
                    dr += 1
            else:
                # Reversed: home_id was away
                hg, ag = r.away_goals, r.home_goals
                if r.outcome == "A":
                    hw += 1  # home_id won (as away)
                elif r.outcome == "H":
                    aw += 1  # away_id won (as home)
                else:
                    dr += 1
            home_goals_total += hg
            away_goals_total += ag
            if hg + ag > 2:
                o25 += 1
            if hg > 0 and ag > 0:
                btts += 1

        home_dominance = round((hw - aw) / total, 4)

        # Recent trend: points from last 3 H2H meetings for home_id
        recent_pts = 0
        for r in rows[:3]:
            if r.home_team_id == home_id:
                recent_pts += 3 if r.outcome == "H" else 1 if r.outcome == "D" else 0
            else:
                recent_pts += 3 if r.outcome == "A" else 1 if r.outcome == "D" else 0
        h2h_recent_trend = round(recent_pts / (3 * 3), 4)  # normalised 0-1

        return {
            "h2h_total_meetings":  total,
            "h2h_home_win_rate":   round(hw / total, 4),
            "h2h_draw_rate":       round(dr / total, 4),
            "h2h_away_win_rate":   round(aw / total, 4),
            "h2h_avg_home_goals":  round(home_goals_total / total, 4),
            "h2h_avg_away_goals":  round(away_goals_total / total, 4),
            "h2h_over_2_5_rate":   round(o25 / total, 4),
            "h2h_btts_rate":       round(btts / total, 4),
            "h2h_home_dominance":  home_dominance,
            "h2h_recent_trend":    h2h_recent_trend,
        }

    # ── TIER 2: Attack/Defense strength (Dixon-Coles parameters) ─────────────

    def _features_attack_defense(
        self,
        home_id: int,
        away_id: int,
        before_dt: datetime,
        season_id: Optional[int],
    ) -> Dict[str, Any]:
        """
        Compute attack/defense strength relative to league average.

        attack_strength  = team_avg_scored   / league_avg_scored
        defense_weakness = team_avg_conceded / league_avg_conceded

        Values > 1.0 mean above-average attack/defense problem.
        """
        season_cond = "AND season_id = :sid" if season_id else ""
        params: Dict[str, Any] = {"dt": before_dt}
        if season_id:
            params["sid"] = season_id

        # League-wide averages
        lg_sql = f"""
            SELECT
                AVG((home_goals + away_goals) / 2.0) AS lg_avg_scored
            FROM "Matches"
            WHERE status = 'FINISHED'
              AND match_datetime < :dt
              AND home_goals IS NOT NULL
              {season_cond}
        """
        lg_row = self._db.execute(text(lg_sql), params).fetchone()
        lg_avg = float(lg_row.lg_avg_scored or self._defaults["form5_avg_scored"])

        def _team_strength(team_id: int) -> Tuple[float, float]:
            t_sql = f"""
                SELECT
                    AVG(CASE WHEN home_team_id=:tid THEN home_goals ELSE away_goals END) AS avg_scored,
                    AVG(CASE WHEN home_team_id=:tid THEN away_goals ELSE home_goals END) AS avg_conceded
                FROM "Matches"
                WHERE (home_team_id=:tid OR away_team_id=:tid)
                  AND status = 'FINISHED'
                  AND match_datetime < :dt
                  AND home_goals IS NOT NULL
                  {season_cond}
            """
            p = dict(params)
            p["tid"] = team_id
            r = self._db.execute(text(t_sql), p).fetchone()
            avg_s = float(r.avg_scored or lg_avg)
            avg_c = float(r.avg_conceded or lg_avg)
            return avg_s / max(lg_avg, 0.01), avg_c / max(lg_avg, 0.01)

        home_atk, home_def_weakness = _team_strength(home_id)
        away_atk, away_def_weakness = _team_strength(away_id)

        # Expected goals (Dixon-Coles style)
        home_xg = home_atk * away_def_weakness * lg_avg * self._config.features.expected_home_goals_multiplier
        away_xg = away_atk * home_def_weakness * lg_avg

        return {
            "home_attack_strength":     round(home_atk, 4),
            "home_defense_weakness":    round(home_def_weakness, 4),
            "away_attack_strength":     round(away_atk, 4),
            "away_defense_weakness":    round(away_def_weakness, 4),
            "expected_home_goals":      round(home_xg, 4),
            "expected_away_goals":      round(away_xg, 4),
            "expected_total_goals":     round(home_xg + away_xg, 4),
            "expected_goal_diff":       round(home_xg - away_xg, 4),
            "league_avg_goals_per_team": round(lg_avg, 4),
        }

    # ── TIER 2: Squad availability ────────────────────────────────────────────

    def _features_squad(
        self,
        home_id: int,
        away_id: int,
        before_dt: datetime,
    ) -> Dict[str, Any]:
        """
        Use the most recent prior match's absence report as a proxy.

        Current-match lineup data may be revised after kickoff, so using it in
        historical training would break the pre-match information boundary.
        """
        def _count_absences(team_id: int) -> Tuple[int, bool]:
            """Returns (total_absences, goalkeeper_absent)."""
            sql = """
                SELECT COUNT(*) AS cnt,
                       SUM(CASE WHEN p.position = 'GK' THEN 1 ELSE 0 END) AS gk_cnt
                FROM "SquadAvailability" sa
                JOIN "Players" p ON p.id = sa.player_id
                JOIN "Matches" m ON m.id = sa.match_id
                WHERE sa.team_id = :tid
                  AND m.id = (
                      SELECT m2.id
                      FROM "Matches" m2
                      JOIN "SquadAvailability" sa2 ON sa2.match_id = m2.id
                      WHERE sa2.team_id = :tid
                        AND m2.match_datetime < :dt
                      ORDER BY m2.match_datetime DESC, m2.id DESC
                      LIMIT 1
                  )
            """
            row = self._db.execute(text(sql), {"tid": team_id, "dt": before_dt}).fetchone()

            cnt = int(row.cnt or 0) if row else 0
            gk_absent = bool(row and row.gk_cnt and row.gk_cnt > 0)
            return cnt, gk_absent

        home_abs, home_gk = _count_absences(home_id)
        away_abs, away_gk = _count_absences(away_id)

        return {
            "home_absences":          home_abs,
            "away_absences":          away_abs,
            "absence_diff":           home_abs - away_abs,
            "home_gk_absent":         int(home_gk),
            "away_gk_absent":         int(away_gk),
            "total_absences":         home_abs + away_abs,
        }

    # ── TIER 2: Referee bias ──────────────────────────────────────────────────

    def _features_referee(
        self, referee_id: Optional[int], before_dt: datetime
    ) -> Dict[str, Any]:
        """Referee historical tendencies (home win rate, cards/game, draw rate)."""
        if not referee_id:
            return {
                "referee_games":          0,
                "referee_home_win_rate":  self._defaults["referee_home_win_rate"],
                "referee_draw_rate":      self._defaults["referee_draw_rate"],
                "referee_avg_yellows":    self._defaults["referee_avg_yellows"],
                "referee_avg_reds":       self._config.features.referee_avg_reds_prior,
                "referee_cards_tendency": 0.0,
            }

        sql = """
            SELECT
                COUNT(*) AS games,
                ROUND(AVG(CASE WHEN m.outcome='H' THEN 1.0 ELSE 0.0 END)::NUMERIC, 4) AS hw_rate,
                ROUND(AVG(CASE WHEN m.outcome='D' THEN 1.0 ELSE 0.0 END)::NUMERIC, 4) AS draw_rate,
                ROUND(AVG(yc.cnt)::NUMERIC, 3) AS avg_yc,
                ROUND(AVG(rc.cnt)::NUMERIC, 3) AS avg_rc
            FROM "Matches" m
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS cnt FROM "MatchEvents" e
                WHERE e.match_id = m.id AND e.event_type = 'yellow card'
            ) yc ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS cnt FROM "MatchEvents" e
                WHERE e.match_id = m.id AND e.event_type = 'red card'
            ) rc ON TRUE
            WHERE m.referee_id = :rid
              AND m.status = 'FINISHED'
              AND m.match_datetime < :dt
        """
        row = self._db.execute(text(sql), {"rid": referee_id, "dt": before_dt}).fetchone()
        games = int(row.games or 0) if row else 0

        if games < self._config.features.min_matches["referee"]:
            return {
                "referee_games":          games,
                "referee_home_win_rate":  self._defaults["referee_home_win_rate"],
                "referee_draw_rate":      self._defaults["referee_draw_rate"],
                "referee_avg_yellows":    self._defaults["referee_avg_yellows"],
                "referee_avg_reds":       self._config.features.referee_avg_reds_prior,
                "referee_cards_tendency": 0.0,
            }

        avg_yc = float(row.avg_yc or self._defaults["referee_avg_yellows"])
        cards_tendency = (avg_yc - self._defaults["referee_avg_yellows"]) / self._config.features.referee_cards_scale

        return {
            "referee_games":          games,
            "referee_home_win_rate":  float(row.hw_rate or self._defaults["referee_home_win_rate"]),
            "referee_draw_rate":      float(row.draw_rate or self._defaults["referee_draw_rate"]),
            "referee_avg_yellows":    avg_yc,
            "referee_avg_reds":       float(row.avg_rc or self._config.features.referee_avg_reds_prior),
            "referee_cards_tendency": round(cards_tendency, 4),
        }

    # ── TIER 2: Rest/fatigue ─────────────────────────────────────────────────

    def _features_rest(
        self, home_id: int, away_id: int, match_dt: datetime
    ) -> Dict[str, Any]:
        """Days since last match for each team."""
        def _days_since_last(team_id: int) -> float:
            sql = """
                SELECT MAX(match_datetime) AS last_dt
                FROM "Matches"
                WHERE (home_team_id = :tid OR away_team_id = :tid)
                  AND status = 'FINISHED'
                  AND match_datetime < :dt
            """
            row = self._db.execute(text(sql), {"tid": team_id, "dt": match_dt}).fetchone()
            if not row or not row.last_dt:
                return self._defaults["rest_days"]
            last = row.last_dt
            if hasattr(last, 'replace'):
                if last.tzinfo is None and match_dt.tzinfo is not None:
                    last = last.replace(tzinfo=timezone.utc)
            diff = (match_dt - last).total_seconds() / 86400.0
            return round(max(1.0, min(diff, self._config.features.rest_days_max)), 2)

        home_rest = _days_since_last(home_id)
        away_rest = _days_since_last(away_id)
        rest_diff = home_rest - away_rest

        home_fatigued = int(home_rest < 4)
        away_fatigued = int(away_rest < 4)

        return {
            "home_rest_days":       home_rest,
            "away_rest_days":       away_rest,
            "rest_days_diff":       round(rest_diff, 2),
            "home_fatigued":        home_fatigued,
            "away_fatigued":        away_fatigued,
            "fatigue_advantage":    away_fatigued - home_fatigued,
        }

    # ── TIER 3: Streaks ───────────────────────────────────────────────────────

    def _features_streaks(
        self, home_id: int, away_id: int, before_dt: datetime
    ) -> Dict[str, Any]:
        """Current win/draw/loss streak for each team."""

        def _streak(team_id: int) -> Dict[str, int]:
            sql = """
                SELECT
                    CASE
                        WHEN home_team_id=:tid AND outcome='H' THEN 'W'
                        WHEN away_team_id=:tid AND outcome='A' THEN 'W'
                        WHEN outcome='D' THEN 'D'
                        ELSE 'L'
                    END AS result
                FROM "Matches"
                WHERE (home_team_id=:tid OR away_team_id=:tid)
                  AND status = 'FINISHED'
                  AND match_datetime < :dt
                ORDER BY match_datetime DESC
                LIMIT 10
            """
            rows = self._db.execute(text(sql), {"tid": team_id, "dt": before_dt}).fetchall()
            results = [r.result for r in rows]
            if not results:
                return {"win_streak": 0, "draw_streak": 0, "loss_streak": 0,
                        "unbeaten_streak": 0, "winless_streak": 0}

            win_streak = 0
            for r in results:
                if r == "W":
                    win_streak += 1
                else:
                    break

            draw_streak = 0
            for r in results:
                if r == "D":
                    draw_streak += 1
                else:
                    break

            loss_streak = 0
            for r in results:
                if r == "L":
                    loss_streak += 1
                else:
                    break

            unbeaten = 0
            for r in results:
                if r in ("W", "D"):
                    unbeaten += 1
                else:
                    break

            winless = 0
            for r in results:
                if r in ("D", "L"):
                    winless += 1
                else:
                    break

            return {
                "win_streak":      win_streak,
                "draw_streak":     draw_streak,
                "loss_streak":     loss_streak,
                "unbeaten_streak": unbeaten,
                "winless_streak":  winless,
            }

        home_streak = _streak(home_id)
        away_streak = _streak(away_id)

        features = {}
        for k, v in home_streak.items():
            features[f"home_{k}"] = v
        for k, v in away_streak.items():
            features[f"away_{k}"] = v
        features["win_streak_advantage"] = home_streak["win_streak"] - away_streak["win_streak"]
        features["momentum_gap"] = home_streak["unbeaten_streak"] - away_streak["unbeaten_streak"]
        return features

    # ── TIER 3: Derby / rivalry ───────────────────────────────────────────────

    def _features_derby(self, home_id: int, away_id: int) -> Dict[str, Any]:
        """Flag if this is a local derby / high-rivalry fixture or top-6 clash."""
        home_name = self._get_team_name(home_id)
        away_name = self._get_team_name(away_id)
        pair = frozenset([home_name, away_name])
        is_derby = int(pair in self._derbies)
        is_top6_clash = int(home_name in self._top_teams and away_name in self._top_teams)
        return {
            "is_derby": is_derby,
            "is_top6_clash": is_top6_clash,
        }

    def _get_team_name(self, team_id: int) -> str:
        row = self._db.execute(
            text('SELECT name FROM "Teams" WHERE id = :id'), {"id": team_id}
        ).fetchone()
        return row.name if row else ""

    # ── TIER 3: Season stage ─────────────────────────────────────────────────

    def _features_season_stage(
        self, match_week: Optional[str], dt: datetime
    ) -> Dict[str, Any]:
        """
        EPL season has 38 rounds.
        Stage affects tactical approach and home advantage.
        """
        try:
            week = int(match_week) if match_week else 19
        except (ValueError, TypeError):
            week = 19

        week_normalized = week / 38.0

        if week <= 10:
            stage = 0   # Early
        elif week <= 28:
            stage = 1   # Mid
        else:
            stage = 2   # Business end / run-in

        month = dt.month
        is_winter = int(month in (11, 12, 1, 2))

        return {
            "match_week":           week,
            "match_week_normalized": round(week_normalized, 4),
            "season_stage":         stage,
            "is_winter_period":     is_winter,
        }

    # ── TIER 3: Team-specific home advantage ─────────────────────────────────

    def _features_home_advantage(
        self, home_id: int, away_id: int, before_dt: datetime
    ) -> Dict[str, Any]:
        """Quantify each team's historical home/away performance split."""
        def _home_adv(team_id: int) -> float:
            sql = """
                WITH home_ppg AS (
                    SELECT AVG(CASE WHEN outcome='H' THEN 3 WHEN outcome='D' THEN 1 ELSE 0 END) AS ppg
                    FROM "Matches"
                    WHERE home_team_id=:tid AND status='FINISHED' AND match_datetime<:dt
                ),
                away_ppg AS (
                    SELECT AVG(CASE WHEN outcome='A' THEN 3 WHEN outcome='D' THEN 1 ELSE 0 END) AS ppg
                    FROM "Matches"
                    WHERE away_team_id=:tid AND status='FINISHED' AND match_datetime<:dt
                )
                SELECT
                    COALESCE(h.ppg, :league_ppg) AS home_ppg,
                    COALESCE(a.ppg, :league_ppg) AS away_ppg
                FROM home_ppg h, away_ppg a
            """
            row = self._db.execute(text(sql), {
                "tid": team_id, "dt": before_dt,
                "league_ppg": self._defaults["season_ppg"],
            }).fetchone()
            if not row:
                return 0.0
            return round(float(row.home_ppg) - float(row.away_ppg), 4)

        home_team_ha = _home_adv(home_id)
        away_team_ha = _home_adv(away_id)

        return {
            "home_team_home_advantage":  home_team_ha,
            "away_team_home_advantage":  away_team_ha,
            "home_advantage_gap":        round(home_team_ha - away_team_ha, 4),
        }

    # ── TIER 4: European competition fatigue ─────────────────────────────────

    def _features_european_fatigue(
        self, home_id: int, away_id: int, match_dt: datetime
    ) -> Dict[str, Any]:
        """Detect if a team played a European/cup match recently."""
        def _played_midweek(team_id: int) -> int:
            week_ago = match_dt - timedelta(days=7)
            sql = """
                SELECT COUNT(*) AS cnt
                FROM "Matches"
                WHERE (home_team_id=:tid OR away_team_id=:tid)
                  AND match_datetime >= :week_ago
                  AND match_datetime < :dt
                  AND status = 'FINISHED'
            """
            row = self._db.execute(
                text(sql), {"tid": team_id, "week_ago": week_ago, "dt": match_dt}
            ).fetchone()
            return int(row.cnt or 0)

        home_recent = _played_midweek(home_id)
        away_recent = _played_midweek(away_id)

        return {
            "home_matches_last_7_days":  home_recent,
            "away_matches_last_7_days":  away_recent,
            "home_european_fatigue":     int(home_recent >= 2),
            "away_european_fatigue":     int(away_recent >= 2),
            "european_fatigue_advantage": int(away_recent >= 2) - int(home_recent >= 2),
        }

    # ── DERIVED: Cross-features (critical for accuracy) ──────────────────────

    def _derived_features(
        self,
        row: Dict[str, Any],
        home_form: Dict[str, Any],
        away_form: Dict[str, Any],
        home_season: Dict[str, Any],
        away_season: Dict[str, Any],
        elo_feats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compute derived/interaction features that combine multiple raw features.
        These are the features that typically give the biggest accuracy boost
        because they capture RELATIVE strength, not just absolute values.
        """
        derived = {}

        # ── Form differentials ───────────────────────────────────────────────
        h_ppg5 = home_form.get("home_form5_ppg", self._defaults["form5_ppg"])
        a_ppg5 = away_form.get("away_form5_ppg", self._defaults["form5_ppg"])
        derived["form5_ppg_diff"] = round(h_ppg5 - a_ppg5, 4)

        h_ppg10 = home_form.get("home_form10_ppg", self._defaults["form5_ppg"])
        a_ppg10 = away_form.get("away_form10_ppg", self._defaults["form5_ppg"])
        derived["form10_ppg_diff"] = round(h_ppg10 - a_ppg10, 4)

        # Momentum differential
        h_mom = home_form.get("home_momentum_score", 0)
        a_mom = away_form.get("away_momentum_score", 0)
        derived["momentum_diff"] = h_mom - a_mom

        # Goals scored differential (form5)
        h_gs = home_form.get("home_form5_avg_scored", self._defaults["form5_avg_scored"])
        a_gs = away_form.get("away_form5_avg_scored", self._defaults["form5_avg_scored"])
        derived["form5_avg_scored_diff"] = round(h_gs - a_gs, 4)

        # Goals conceded differential (form5) - lower = better defense
        h_gc = home_form.get("home_form5_avg_conceded", self._defaults["form5_avg_conceded"])
        a_gc = away_form.get("away_form5_avg_conceded", self._defaults["form5_avg_conceded"])
        derived["form5_avg_conceded_diff"] = round(h_gc - a_gc, 4)

        # ── Season differentials ─────────────────────────────────────────────
        h_sppg = home_season.get("home_season_ppg", self._defaults["season_ppg"])
        a_sppg = away_season.get("away_season_ppg", self._defaults["season_ppg"])
        derived["season_ppg_diff"] = round(h_sppg - a_sppg, 4)

        h_swr = home_season.get("home_season_win_rate", self._defaults["h2h_home_win_rate"])
        a_swr = away_season.get("away_season_win_rate", self._defaults["h2h_home_win_rate"])
        derived["season_win_rate_diff"] = round(h_swr - a_swr, 4)

        h_sgd = home_season.get("home_season_gd", 0.0)
        a_sgd = away_season.get("away_season_gd", 0.0)
        derived["season_gd_diff"] = round(h_sgd - a_sgd, 4)

        # ── xG overperformance (form goals vs expected) ──────────────────────
        exp_hg = row.get("expected_home_goals", self._defaults["form5_avg_scored"])
        exp_ag = row.get("expected_away_goals", self._defaults["form5_avg_scored"])
        derived["home_xg_overperformance"] = round(h_gs - exp_hg, 4) if exp_hg else 0.0
        derived["away_xg_overperformance"] = round(a_gs - exp_ag, 4) if exp_ag else 0.0

        # ── Composite power rating ───────────────────────────────────────────
        # Blend of ELO + form + season into single team strength metric
        elo_diff = elo_feats.get("elo_diff", 0.0)
        # Normalise ELO diff to ~0-1 scale for blending
        elo_norm = elo_diff / self._elo_config.rating_scale
        form_norm = (h_ppg5 - a_ppg5) / 3.0  # max PPG diff ≈ 3
        season_norm = (h_sppg - a_sppg) / 3.0
        derived["composite_power_rating"] = round(
            0.5 * elo_norm + 0.3 * form_norm + 0.2 * season_norm, 4
        )

        # ── Draw risk indicator ──────────────────────────────────────────────
        # Higher when: teams are evenly matched + both have defensive form
        abs_elo_diff = abs(elo_diff)
        draw_indicator = max(0.0, 1.0 - abs_elo_diff / 300.0) * (
            0.5 * (h_gc + a_gc) / max(h_gs + a_gs, 0.01)
        )
        derived["draw_risk_indicator"] = round(min(draw_indicator, 1.0), 4)

        return derived

    # ── DB helpers ────────────────────────────────────────────────────────────

    def _fetch_match_meta(self, match_id: int) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT
                m.id, m.home_team_id, m.away_team_id,
                m.match_datetime, m.match_week, m.season_id,
                m.referee_id, m.outcome, m.status,
                s.name AS season_name,
                ht.name AS home_team_name,
                at.name AS away_team_name
            FROM "Matches" m
            JOIN "Seasons" s ON s.id = m.season_id
            JOIN "Teams" ht ON ht.id = m.home_team_id
            JOIN "Teams" at ON at.id = m.away_team_id
            WHERE m.id = :mid
        """
        row = self._db.execute(text(sql), {"mid": match_id}).fetchone()
        if not row:
            return None

        dt = row.match_datetime
        if dt and hasattr(dt, 'replace') and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return {
            "match_id":      row.id,
            "home_team_id":  row.home_team_id,
            "away_team_id":  row.away_team_id,
            "match_datetime": dt,
            "match_week":    row.match_week,
            "season_id":     row.season_id,
            "season_name":   row.season_name,
            "referee_id":    row.referee_id,
            "outcome":       row.outcome,
            "status":        row.status,
            "home_team_name": row.home_team_name,
            "away_team_name": row.away_team_name,
        }

    def _fetch_all_finished_matches(
        self,
        season_name: Optional[str],
        min_match_week: int,
    ) -> List[Dict[str, Any]]:
        """Fetch metadata for all finished matches to build training set."""
        params: Dict[str, Any] = {}
        filters = ["m.status = 'FINISHED'", "m.home_goals IS NOT NULL"]

        if season_name:
            filters.append("s.name = :season")
            params["season"] = season_name

        if min_match_week:
            filters.append("CAST(m.match_week AS INTEGER) >= :min_mw")
            params["min_mw"] = min_match_week

        where = "WHERE " + " AND ".join(filters)

        sql = f"""
            SELECT
                m.id, m.home_team_id, m.away_team_id,
                m.match_datetime, m.match_week, m.season_id,
                m.referee_id, m.outcome,
                s.name AS season_name,
                ht.name AS home_team_name,
                at.name AS away_team_name
            FROM "Matches" m
            JOIN "Seasons" s ON s.id = m.season_id
            JOIN "Teams" ht  ON ht.id = m.home_team_id
            JOIN "Teams" at  ON at.id = m.away_team_id
            {where}
            ORDER BY m.match_datetime ASC
        """
        rows = self._db.execute(text(sql), params).fetchall()
        result = []
        for row in rows:
            dt = row.match_datetime
            if dt and hasattr(dt, 'replace') and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            result.append({
                "match_id":       row.id,
                "home_team_id":   row.home_team_id,
                "away_team_id":   row.away_team_id,
                "match_datetime": dt,
                "match_week":     row.match_week,
                "season_id":      row.season_id,
                "season_name":    row.season_name,
                "referee_id":     row.referee_id,
                "outcome":        row.outcome,
                "home_team_name": row.home_team_name,
                "away_team_name": row.away_team_name,
            })
        return result
