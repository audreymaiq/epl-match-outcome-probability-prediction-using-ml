"""
Unit tests for EloCalculator - pure math, no DB or network required.

Actual method signatures (confirmed from source):
  - update(home_elo, away_elo, home_goals, away_goals, match_week, is_top6_clash)
      → Tuple[float, float]
  - elo_to_win_probability(home_elo, away_elo, apply_home_advantage)
      → Tuple[float, float, float]  - (p_home, p_draw, p_away)
  - season_regression(elo) → float
  - _goal_diff_multiplier(gd, actual_home, actual_away) → float
  - expected_score(elo_a, elo_b) → float
"""
import pytest
from ml.elo.elo_calculator import EloCalculator


@pytest.fixture
def calc() -> EloCalculator:
    return EloCalculator()


class TestEloUpdates:
    """Tests for update() - direction and zero-sum property."""

    def test_home_win_increases_home_elo(self, calc):
        home_new, _ = calc.update(1500, 1500, 1, 0)
        assert home_new > 1500

    def test_home_win_decreases_away_elo(self, calc):
        _, away_new = calc.update(1500, 1500, 1, 0)
        assert away_new < 1500

    def test_home_win_is_zero_sum(self, calc):
        """ELO gain by home must equal ELO lost by away."""
        home_new, away_new = calc.update(1500, 1500, 1, 0)
        delta_home = home_new - 1500
        delta_away = away_new - 1500
        assert abs(delta_home + delta_away) < 0.01

    def test_away_win_increases_away_elo(self, calc):
        _, away_new = calc.update(1500, 1500, 0, 1)
        assert away_new > 1500

    def test_away_win_decreases_home_elo(self, calc):
        home_new, _ = calc.update(1500, 1500, 0, 1)
        assert home_new < 1500

    def test_draw_small_changes_equal_teams(self, calc):
        """Equal teams drawing should barely change ELO."""
        home_new, away_new = calc.update(1500, 1500, 0, 0)
        assert abs(home_new - 1500) < 25
        assert abs(away_new - 1500) < 25

    def test_draw_zero_sum(self, calc):
        home_new, away_new = calc.update(1500, 1500, 0, 0)
        assert abs((home_new - 1500) + (away_new - 1500)) < 0.01

    def test_expected_win_small_elo_change(self, calc):
        """Strong team (1700) beating weak team (1300) → small gain (expected)."""
        home_new, _ = calc.update(1700, 1300, 1, 0)
        delta = home_new - 1700
        assert 0 < delta < 12  # expected win → small gain

    def test_upset_large_elo_change(self, calc):
        """Weak team (1300) beating strong (1700) at home → large gain (upset)."""
        home_new, _ = calc.update(1300, 1700, 1, 0)
        delta = home_new - 1300
        assert delta > 15  # upset → large gain


class TestEloProbabilities:
    """Tests for elo_to_win_probability() - (p_home, p_draw, p_away) tuple."""

    def test_probs_sum_to_one(self, calc):
        p_h, p_d, p_a = calc.elo_to_win_probability(1600, 1400)
        assert abs(p_h + p_d + p_a - 1.0) < 1e-4

    def test_all_probs_positive(self, calc):
        p_h, p_d, p_a = calc.elo_to_win_probability(1600, 1400)
        assert p_h > 0
        assert p_d > 0
        assert p_a > 0

    def test_home_advantage_at_equal_elo(self, calc):
        """Home team should have higher win prob at equal ELO (home advantage)."""
        p_h, _, p_a = calc.elo_to_win_probability(1500, 1500)
        assert p_h > p_a

    def test_higher_elo_higher_win_prob(self, calc):
        p_h_strong, _, _ = calc.elo_to_win_probability(1800, 1200)
        p_h_equal, _, _ = calc.elo_to_win_probability(1500, 1500)
        assert p_h_strong > p_h_equal

    def test_extreme_elo_gap_near_certain(self, calc):
        """2000 vs 1000: home team should be strongly favored.
        Note: draw probability is always retained (~15-25%), so home_win < 0.85.
        """
        p_h, p_d, p_a = calc.elo_to_win_probability(2000, 1000)
        assert p_h > 0.70   # home is strongly favored
        assert p_h > p_a    # home > away (obvious)
        assert p_d > 0.0    # draws are always possible
        assert p_a < 0.10   # away win is unlikely

    def test_no_home_advantage_flag(self, calc):
        """With apply_home_advantage=False, equal ELO → roughly equal H/A probs."""
        p_h, _, p_a = calc.elo_to_win_probability(1500, 1500, apply_home_advantage=False)
        assert abs(p_h - p_a) < 0.05  # should be roughly symmetric


class TestSeasonRegression:
    """Tests for season_regression() - mean-reverting."""

    def test_high_elo_pulled_down(self, calc):
        regressed = calc.season_regression(1800)
        assert 1500 < regressed < 1800

    def test_low_elo_pulled_up(self, calc):
        regressed = calc.season_regression(1200)
        assert 1200 < regressed < 1500

    def test_mean_elo_unchanged(self, calc):
        """1500 (the mean) should be unchanged after regression."""
        regressed = calc.season_regression(1500)
        assert abs(regressed - 1500) < 1.0


class TestGoalDifferenceMultiplier:
    """Tests for _goal_diff_multiplier(gd, actual_home, actual_away)."""

    def test_larger_gd_larger_multiplier(self, calc):
        m1 = calc._goal_diff_multiplier(1, 1.0, 0.0)  # 1-goal home win
        m3 = calc._goal_diff_multiplier(3, 1.0, 0.0)  # 3-goal home win
        m5 = calc._goal_diff_multiplier(5, 1.0, 0.0)  # 5-goal home win
        assert m3 > m1
        assert m5 >= m3

    def test_multiplier_at_least_one(self, calc):
        m = calc._goal_diff_multiplier(1, 1.0, 0.0)
        assert m >= 1.0

    def test_multiplier_capped(self, calc):
        """Very large GD should not produce unreasonably huge multiplier."""
        m_large = calc._goal_diff_multiplier(20, 1.0, 0.0)
        assert m_large < 10.0  # Must be bounded

    def test_zero_gd_gives_one(self, calc):
        """GD of 0 (draw) should give multiplier = 1."""
        m = calc._goal_diff_multiplier(0, 0.5, 0.5)
        assert m == pytest.approx(1.0, abs=0.01)


class TestExpectedScore:
    """Tests for expected_score() - standard ELO logistic."""

    def test_equal_elos_fifty_percent(self, calc):
        score = calc.expected_score(1500, 1500)
        assert score == pytest.approx(0.5, abs=1e-6)

    def test_higher_elo_higher_expected(self, calc):
        score_strong = calc.expected_score(1700, 1300)
        score_equal = calc.expected_score(1500, 1500)
        assert score_strong > score_equal

    def test_expected_between_zero_and_one(self, calc):
        for elo_diff in [-500, -100, 0, 100, 500]:
            s = calc.expected_score(1500 + elo_diff, 1500)
            assert 0.0 < s < 1.0
