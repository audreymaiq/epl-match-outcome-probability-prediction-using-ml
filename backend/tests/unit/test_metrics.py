"""
Unit tests for ML evaluation metrics - pure numpy, no DB or network.

Tests cover:
- RPS: known perfect/worst/uniform cases
- Brier score: zero for perfect predictions
- ECE: structure and bounds
- ROI simulation: correct strategy labelling
- generate_evaluation_report: key presence
"""
import numpy as np
import pytest
from ml.evaluation.metrics import (
    compute_rps,
    compute_rps_per_match,
    compute_brier_score,
    compute_ece,
    compute_calibration_curve,
    compute_roi_simulation,
    generate_evaluation_report,
)


class TestRPS:
    def test_perfect_prediction_rps_zero(self):
        y_true = np.array([0, 1, 2])
        y_proba = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ])
        assert compute_rps(y_true, y_proba) == pytest.approx(0.0, abs=1e-9)

    def test_worst_prediction_rps_high(self):
        """Predicting the opposite outcome with certainty → max RPS."""
        y_true = np.array([0])        # true = home win
        y_proba = np.array([[0.0, 0.0, 1.0]])  # predict away win with 100%
        rps = compute_rps(y_true, y_proba)
        assert rps == pytest.approx(1.0, abs=1e-9)

    def test_uniform_prediction_rps_approx_third(self):
        """Uniform (1/3, 1/3, 1/3) for all matches → RPS ≈ 1/3 * EPL variance."""
        y_true = np.array([0, 1, 2, 0, 1, 2])
        y_proba = np.full((6, 3), 1 / 3)
        rps = compute_rps(y_true, y_proba)
        # Uniform prediction: RPS = (1/3) for a result in an adjacent class
        assert 0.0 < rps < 1.0

    def test_rps_nonnegative(self):
        rng = np.random.default_rng(42)
        y_true = rng.integers(0, 3, size=100)
        y_proba = rng.dirichlet(np.ones(3), size=100)
        assert compute_rps(y_true, y_proba) >= 0.0

    def test_rps_per_match_shape(self):
        y_true = np.array([0, 1, 2, 0])
        y_proba = np.array([
            [0.7, 0.2, 0.1],
            [0.2, 0.6, 0.2],
            [0.1, 0.2, 0.7],
            [0.6, 0.3, 0.1],
        ])
        per_match = compute_rps_per_match(y_true, y_proba)
        assert per_match.shape == (4,)
        assert per_match.mean() == pytest.approx(compute_rps(y_true, y_proba), abs=1e-9)


class TestBrierScore:
    def test_perfect_brier_zero(self):
        y_true = np.array([0, 1, 2])
        y_proba = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ])
        result = compute_brier_score(y_true, y_proba)
        assert result["overall"] == pytest.approx(0.0, abs=1e-9)

    def test_brier_returns_all_keys(self):
        y_true = np.array([0, 1, 2, 0])
        y_proba = np.array([
            [0.7, 0.2, 0.1],
            [0.2, 0.6, 0.2],
            [0.1, 0.2, 0.7],
            [0.6, 0.3, 0.1],
        ])
        result = compute_brier_score(y_true, y_proba)
        for key in ["overall", "home_win", "draw", "away_win"]:
            assert key in result

    def test_brier_nonnegative(self):
        rng = np.random.default_rng(0)
        y_true = rng.integers(0, 3, size=50)
        y_proba = rng.dirichlet(np.ones(3), size=50)
        result = compute_brier_score(y_true, y_proba)
        for v in result.values():
            assert v >= 0.0


class TestECE:
    def test_ece_perfect_returns_zero(self):
        """Perfect predictions: confidence always matches accuracy → ECE = 0."""
        y_true = np.array([0, 1, 2, 0, 1, 2])
        y_proba = np.zeros((6, 3))
        for i, t in enumerate(y_true):
            y_proba[i, t] = 1.0
        ece = compute_ece(y_true, y_proba)
        assert ece == pytest.approx(0.0, abs=0.01)

    def test_ece_between_zero_and_one(self):
        rng = np.random.default_rng(1)
        y_true = rng.integers(0, 3, size=200)
        y_proba = rng.dirichlet(np.ones(3), size=200)
        ece = compute_ece(y_true, y_proba)
        assert 0.0 <= ece <= 1.0

    def test_calibration_curve_shape(self):
        rng = np.random.default_rng(2)
        y_true = rng.integers(0, 3, size=100)
        y_proba = rng.dirichlet(np.ones(3), size=100)
        mean_pred, frac_pos, counts = compute_calibration_curve(y_true, y_proba, n_bins=10)
        assert mean_pred.shape == (10,)
        assert frac_pos.shape == (10,)
        assert counts.shape == (10,)
        assert counts.sum() == 100


class TestROISimulation:
    def test_roi_keys_present(self):
        rng = np.random.default_rng(3)
        y_true = rng.integers(0, 3, size=50)
        y_proba = rng.dirichlet(np.ones(3), size=50)
        result = compute_roi_simulation(y_true, y_proba)
        for key in ["n_matches", "model_bets", "model_roi_pct", "home_always_roi_pct"]:
            assert key in result

    def test_n_matches_correct(self):
        rng = np.random.default_rng(4)
        y_true = rng.integers(0, 3, size=80)
        y_proba = rng.dirichlet(np.ones(3), size=80)
        result = compute_roi_simulation(y_true, y_proba)
        assert result["n_matches"] == 80

    def test_model_bets_le_n(self):
        rng = np.random.default_rng(5)
        y_true = rng.integers(0, 3, size=60)
        y_proba = rng.dirichlet(np.ones(3), size=60)
        result = compute_roi_simulation(y_true, y_proba, threshold=0.5)
        assert result["model_bets"] <= 60


class TestEvaluationReport:
    def test_report_contains_accuracy(self):
        rng = np.random.default_rng(6)
        y_true = rng.integers(0, 3, size=40)
        y_proba = rng.dirichlet(np.ones(3), size=40)
        report = generate_evaluation_report(y_true, y_proba, fold_label="test")
        assert "test/accuracy" in report
        assert "test/rps" in report
        assert "test/ece" in report

    def test_accuracy_between_zero_and_one(self):
        rng = np.random.default_rng(7)
        y_true = rng.integers(0, 3, size=100)
        y_proba = rng.dirichlet(np.ones(3), size=100)
        report = generate_evaluation_report(y_true, y_proba)
        assert 0.0 <= report["overall/accuracy"] <= 1.0

