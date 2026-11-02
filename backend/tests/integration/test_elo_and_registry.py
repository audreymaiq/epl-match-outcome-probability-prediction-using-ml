"""
Integration smoke tests for ELO and provider registry.

No DB required - tests importability, registry auto-discovery,
and ELO correctness on multi-match simulations.
"""
import pytest
from ml.elo.elo_calculator import EloCalculator


class TestEloIntegration:
    def test_elo_calculator_instantiates(self):
        calc = EloCalculator()
        assert calc is not None

    def test_full_season_simulation(self):
        """Simulate 10 matches; ELO must stay in sane range."""
        calc = EloCalculator()
        home_elo, away_elo = 1500.0, 1500.0

        fixtures = [(1, 0), (0, 1), (1, 1), (2, 0), (0, 0),
                    (3, 1), (1, 2), (0, 0), (1, 0), (2, 2)]
        for week, (hg, ag) in enumerate(fixtures, start=5):
            home_elo, away_elo = calc.update(home_elo, away_elo, hg, ag, match_week=week)

        assert 1200 < home_elo < 1800
        assert 1200 < away_elo < 1800

    def test_probabilities_sum_to_one(self):
        calc = EloCalculator()
        for home_elo, away_elo in [(1500, 1500), (1700, 1300), (1300, 1700), (2000, 1000)]:
            p_h, p_d, p_a = calc.elo_to_win_probability(home_elo, away_elo)
            assert abs(p_h + p_d + p_a - 1.0) < 1e-4

    def test_elo_extreme_mismatch(self):
        calc = EloCalculator()
        p_h, p_d, p_a = calc.elo_to_win_probability(2000, 1000)
        assert p_h > 0.70  # strongly favored
        assert p_h > p_a
        assert p_d > 0.0   # draws always possible
        assert abs(p_h + p_d + p_a - 1.0) < 1e-4

    def test_season_regression_reduces_spread(self):
        calc = EloCalculator()
        # Teams from ELO 1000 to 1950 (step 50)
        teams = {f"team_{i}": 1000.0 + i * 50 for i in range(20)}
        original_spread = max(teams.values()) - min(teams.values())

        for team, elo in teams.items():
            teams[team] = calc.season_regression(elo)

        new_spread = max(teams.values()) - min(teams.values())
        # Regression must reduce the spread (pull toward 1500)
        assert new_spread < original_spread
        # Values must stay within ELO clamp bounds (800–2200)
        assert min(teams.values()) > 800
        assert max(teams.values()) < 2200


class TestProviderRegistry:
    """Test provider auto-discovery - no network required."""

    def test_providers_module_importable(self):
        from providers.base.provider_registry import ProviderRegistry, discover_providers
        assert ProviderRegistry is not None
        assert callable(discover_providers)

    def test_discover_providers_returns_list(self):
        from providers.base.provider_registry import discover_providers
        providers = discover_providers()
        assert isinstance(providers, list)

    def test_sofascore_provider_self_registers(self):
        from providers.base.provider_registry import ProviderRegistry
        try:
            import providers.sofascore.provider  # noqa: F401 - triggers self-registration
            available = ProviderRegistry.available_providers()
            assert "sofascore" in available
        except ImportError:
            pytest.skip("SofaScore provider dependencies not available")


class TestMetricsIntegration:
    """Smoke test for the metrics module."""

    def test_rps_import_and_run(self):
        import numpy as np
        from ml.evaluation.metrics import compute_rps, generate_evaluation_report
        y_true = np.array([0, 1, 2, 0, 1, 2])
        y_proba = np.array([
            [0.7, 0.2, 0.1],
            [0.2, 0.6, 0.2],
            [0.1, 0.2, 0.7],
            [0.6, 0.3, 0.1],
            [0.3, 0.5, 0.2],
            [0.1, 0.3, 0.6],
        ])
        rps = compute_rps(y_true, y_proba)
        assert 0.0 <= rps <= 1.0

        report = generate_evaluation_report(y_true, y_proba, fold_label="smoke")
        assert "smoke/accuracy" in report
        assert "smoke/rps" in report

    def test_calibrator_import_and_run(self):
        import numpy as np
        from ml.evaluation.calibration import MulticlassIsotonicCalibrator
        rng = np.random.default_rng(99)
        y_true = rng.integers(0, 3, size=100)
        y_proba = rng.dirichlet(np.ones(3), size=100)
        cal = MulticlassIsotonicCalibrator(n_classes=3)
        out = cal.fit_transform(y_true, y_proba)
        assert out.shape == (100, 3)
        assert abs(out.sum(axis=1).mean() - 1.0) < 1e-5
