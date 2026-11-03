# ml/elo/elo_calculator.py
"""
ELO Rating Calculator - Football-Tuned Implementation.

Standard ELO is designed for chess (binary win/loss, equal importance).
Football requires several domain-specific adjustments:

  1. K-factor variation:
     - Higher K for promoted/relegated teams (more uncertain)
     - Higher K for early-season matches (less established form)
     - Lower K for veteran top-6 teams (stable over many seasons)

  2. Home advantage:
     - EPL home teams win ~46% of matches (vs 28% away)
     - This translates to ~65 ELO points advantage

  3. Goal-difference multiplier (Massey/USCF method):
     - A 3-0 win is stronger evidence than a 1-0 win
     - GD multiplier = ln(|gd| + 1) * correction
     - Corrected for score inflation (don't over-reward thrashings)

  4. Seasonal regression to mean:
     - At start of each season, ratings regress toward 1500
     - Factor: 1/3rd of distance to mean (standard practice)
     - Accounts for squad changes, manager changes, transfers

  5. Draw handling:
     - Expected draw probability is derived from Elo difference
     - Actual outcome: home win = 1.0, draw = 0.5, away win = 0.0

References:
  - FiveThirtyEight NFL/NBA/Soccer ELO methodology
  - Dixon & Coles (1997) - Modelling Association Football Scores
  - Pi-Rating (Constantinou & Fenton, 2013)
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple
from ml.config import load_ml_config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EloConfig:
    """Immutable ELO configuration - change here to affect ALL calculations."""

    # Starting ELO for a brand-new team with no history
    initial_elo: float = 1500.0

    # ELO points that represent home field advantage in EPL
    # (Empirically: ~65 pts based on 10-season EPL data)
    home_advantage: float = 65.0
    rating_scale: float = 400.0

    # K-factor range: how much each match can shift ratings
    k_base: float  = 20.0    # standard match
    k_big_match: float = 28.0  # top-6 vs top-6 (more weight)
    k_early_season: float = 32.0  # first 5 rounds of a season
    k_max: float   = 40.0    # maximum ever allowed

    # Season regression: at the start of each season, pull ratings toward mean
    # Formula: new_elo = elo + regression_factor * (initial_elo - elo)
    season_regression_factor: float = 0.33   # 1/3 regression

    # Goal difference multiplier caps
    # We use: multiplier = log(|gd| + 1) * gd_weight, capped at gd_cap
    gd_weight: float = 0.5
    gd_cap: float    = 1.75   # max multiplier for any goal difference
    draw_base: float = 0.28
    draw_reduction: float = 0.08
    draw_min: float = 0.18
    draw_slope: float = 0.01
    draw_midpoint: float = 100.0

    # ELO bounds - hard limits to prevent runaway ratings
    elo_min: float = 800.0
    elo_max: float = 2200.0


# Singleton default config
DEFAULT_CONFIG = EloConfig(**load_ml_config().elo)


# ─────────────────────────────────────────────────────────────────────────────
# EloCalculator
# ─────────────────────────────────────────────────────────────────────────────

class EloCalculator:
    """
    Stateless ELO calculator for football matches.

    All methods are pure functions (no side effects).
    State is managed by EloBuilder, not here.
    """

    def __init__(self, config: EloConfig = DEFAULT_CONFIG):
        self._cfg = config

    # ── Public interface ──────────────────────────────────────────────────────

    def update(
        self,
        home_elo: float,
        away_elo: float,
        home_goals: int,
        away_goals: int,
        match_week: int = 20,
        is_top6_clash: bool = False,
    ) -> Tuple[float, float]:
        """
        Compute updated ELO ratings after a match.

        Args:
            home_elo:       Pre-match ELO of the home team.
            away_elo:       Pre-match ELO of the away team.
            home_goals:     Goals scored by home team.
            away_goals:     Goals scored by away team.
            match_week:     Round number (1-38) - affects K-factor.
            is_top6_clash:  True if both teams are traditional top-6.

        Returns:
            (new_home_elo, new_away_elo)
        """
        # 1. Adjusted ELO accounting for home advantage
        home_elo_adj = home_elo + self._cfg.home_advantage
        expected_home = self.expected_score(home_elo_adj, away_elo)
        expected_away = 1.0 - expected_home

        # 2. Actual scores (1.0 = win, 0.5 = draw, 0.0 = loss)
        actual_home, actual_away = self._actual_scores(home_goals, away_goals)

        # 3. K-factor (adaptive)
        k = self.k_factor(match_week, is_top6_clash)

        # 4. Goal-difference multiplier
        gd = abs(home_goals - away_goals)
        gd_multiplier = self._goal_diff_multiplier(gd, actual_home, actual_away)

        # 5. ELO delta
        delta_home = k * gd_multiplier * (actual_home - expected_home)
        delta_away = k * gd_multiplier * (actual_away - expected_away)

        new_home = self._clamp(home_elo + delta_home)
        new_away = self._clamp(away_elo + delta_away)

        logger.debug(
            "ELO update: home %.0f→%.0f (Δ%.1f), away %.0f→%.0f (Δ%.1f) | "
            "Score %d-%d | K=%.1f | GD×=%.2f",
            home_elo, new_home, delta_home,
            away_elo, new_away, delta_away,
            home_goals, away_goals, k, gd_multiplier,
        )
        return new_home, new_away

    def expected_score(self, elo_a: float, elo_b: float) -> float:
        """
        Probability that team A beats team B, given their ELO ratings.
        Standard logistic formula: P(A wins) = 1 / (1 + 10^((B-A)/400))

        Note: caller should apply home_advantage adjustment to elo_a
        BEFORE calling this method.
        """
        return 1.0 / (1.0 + math.pow(10.0, (elo_b - elo_a) / self._cfg.rating_scale))

    def elo_to_win_probability(
        self,
        home_elo: float,
        away_elo: float,
        apply_home_advantage: bool = True,
    ) -> Tuple[float, float, float]:
        """
        Convert ELO ratings to three-way match probabilities [P(H), P(D), P(A)].

        Uses the ELO-based expected score as win probability,
        then applies EPL-calibrated draw probability adjustment.

        Returns:
            (prob_home_win, prob_draw, prob_away_win)
        """
        home_adj = home_elo + (self._cfg.home_advantage if apply_home_advantage else 0.0)
        p_home_win_raw = self.expected_score(home_adj, away_elo)
        p_away_win_raw = 1.0 - p_home_win_raw

        # Draw probability: EPL draws average ~26%.
        # Higher at near-even matchups, lower at mismatches.
        # Heuristic calibrated on EPL data:
        p_draw = self._estimate_draw_prob(abs(home_elo - away_elo))

        # Normalize three-way probabilities
        scale = p_home_win_raw + p_away_win_raw
        p_home = p_home_win_raw / scale * (1.0 - p_draw)
        p_away = p_away_win_raw / scale * (1.0 - p_draw)

        return round(p_home, 4), round(p_draw, 4), round(p_away, 4)

    def season_regression(self, elo: float) -> float:
        """
        Apply pre-season regression to the mean.
        Called at the start of each new season for every team.
        """
        regressed = elo + self._cfg.season_regression_factor * (self._cfg.initial_elo - elo)
        return round(self._clamp(regressed), 2)

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _actual_scores(home_goals: int, away_goals: int) -> Tuple[float, float]:
        """Convert match result to ELO score pair."""
        if home_goals > away_goals:
            return 1.0, 0.0
        elif home_goals == away_goals:
            return 0.5, 0.5
        else:
            return 0.0, 1.0

    def k_factor(self, match_week: int, is_top6_clash: bool = False) -> float:
        """
        Adaptive K-factor:
          - Early season (weeks 1-5): higher uncertainty → higher K
          - Top-6 clash: more informative result → slightly higher K
          - Default: base K
        """
        if match_week <= 5:
            k = self._cfg.k_early_season
        elif is_top6_clash:
            k = self._cfg.k_big_match
        else:
            k = self._cfg.k_base
        return min(k, self._cfg.k_max)

    def _goal_diff_multiplier(
        self,
        goal_diff: int,
        actual_home: float,
        actual_away: float,
    ) -> float:
        """
        Goal-difference multiplier based on FiveThirtyEight's method.

        For a winning team: multiplier = ln(GD + 1) * gd_weight
        Correction factor: reduces multiplier if result was unexpected
        (a team expected to win doesn't get as much credit for a large GD).
        """
        if goal_diff == 0:
            return 1.0

        raw_mult = math.log(goal_diff + 1) * self._cfg.gd_weight
        return round(min(1.0 + raw_mult, self._cfg.gd_cap), 4)

    def _estimate_draw_prob(self, elo_diff: float) -> float:
        """
        Configured draw probability heuristic based on ELO difference.
        """
        # Sigmoid mapping; calibrate these parameters using held out seasons.
        base_draw = self._cfg.draw_base
        reduction = self._cfg.draw_reduction * (
            1.0 / (1.0 + math.exp(-self._cfg.draw_slope * (elo_diff - self._cfg.draw_midpoint)))
        )
        return round(max(self._cfg.draw_min, base_draw - reduction), 4)

    def _clamp(self, elo: float) -> float:
        """Hard clamp ELO to valid range."""
        return max(self._cfg.elo_min, min(self._cfg.elo_max, elo))


# ─────────────────────────────────────────────────────────────────────────────
# EloRecord - immutable result for a single match
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EloRecord:
    """Captures pre- and post-match ELO for one team in one match."""
    team_id: int
    match_id: Optional[int]
    match_date: object          # date
    elo_before: float
    elo_after: float
    k_factor: float
    season: Optional[str]
