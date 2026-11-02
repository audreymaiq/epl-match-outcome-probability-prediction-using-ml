"""
Unit tests for MulticlassIsotonicCalibrator.

Tests cover:
- Output shape matches input
- Output rows sum to 1 (simplex constraint)
- All values in [0, 1]
- fit_transform convenience method
- RuntimeError if transform() before fit()
"""
import numpy as np
import pytest
from ml.evaluation.calibration import MulticlassIsotonicCalibrator, compute_reliability_data


@pytest.fixture
def sample_data():
    rng = np.random.default_rng(42)
    y_true = rng.integers(0, 3, size=200)
    y_proba = rng.dirichlet(np.ones(3), size=200)
    return y_true, y_proba


class TestMulticlassIsotonicCalibrator:
    def test_output_shape_preserved(self, sample_data):
        y_true, y_proba = sample_data
        cal = MulticlassIsotonicCalibrator()
        cal.fit(y_true, y_proba)
        out = cal.transform(y_proba)
        assert out.shape == y_proba.shape

    def test_rows_sum_to_one(self, sample_data):
        y_true, y_proba = sample_data
        cal = MulticlassIsotonicCalibrator()
        out = cal.fit_transform(y_true, y_proba)
        row_sums = out.sum(axis=1)
        np.testing.assert_allclose(row_sums, 1.0, atol=1e-6)

    def test_all_values_in_unit_interval(self, sample_data):
        y_true, y_proba = sample_data
        cal = MulticlassIsotonicCalibrator()
        out = cal.fit_transform(y_true, y_proba)
        assert (out >= 0).all()
        assert (out <= 1).all()

    def test_transform_before_fit_raises(self):
        cal = MulticlassIsotonicCalibrator()
        with pytest.raises(RuntimeError, match="fit()"):
            cal.transform(np.array([[0.4, 0.3, 0.3]]))

    def test_is_fitted_flag(self, sample_data):
        y_true, y_proba = sample_data
        cal = MulticlassIsotonicCalibrator()
        assert not cal.is_fitted
        cal.fit(y_true, y_proba)
        assert cal.is_fitted

    def test_fit_transform_same_as_separate(self, sample_data):
        y_true, y_proba = sample_data
        cal1 = MulticlassIsotonicCalibrator()
        out1 = cal1.fit_transform(y_true, y_proba)

        cal2 = MulticlassIsotonicCalibrator()
        cal2.fit(y_true, y_proba)
        out2 = cal2.transform(y_proba)

        np.testing.assert_allclose(out1, out2, atol=1e-10)


class TestReliabilityData:
    def test_returns_expected_keys(self, sample_data):
        y_true, y_proba = sample_data
        result = compute_reliability_data(y_true, y_proba, class_idx=0)
        for key in ["class", "mean_predicted", "fraction_of_positives", "counts", "ece_class"]:
            assert key in result

    def test_class_name_correct(self, sample_data):
        y_true, y_proba = sample_data
        assert compute_reliability_data(y_true, y_proba, class_idx=0)["class"] == "home_win"
        assert compute_reliability_data(y_true, y_proba, class_idx=1)["class"] == "draw"
        assert compute_reliability_data(y_true, y_proba, class_idx=2)["class"] == "away_win"

    def test_ece_nonnegative(self, sample_data):
        y_true, y_proba = sample_data
        for cls_idx in range(3):
            result = compute_reliability_data(y_true, y_proba, class_idx=cls_idx)
            assert result["ece_class"] >= 0.0

