import numpy as np
import pandas as pd
import pytest
import joblib
from sklearn.linear_model import LogisticRegression

from ml.training import train as training_module


def test_stacking_ensemble_uses_chronological_oof_and_returns_probabilities(monkeypatch, tmp_path):
    monkeypatch.setattr(
        training_module,
        "_make_xgboost",
        lambda params=None: LogisticRegression(max_iter=300),
    )
    monkeypatch.setattr(
        training_module,
        "_make_lightgbm",
        lambda params=None: LogisticRegression(max_iter=300),
    )
    monkeypatch.setattr(
        training_module,
        "_make_catboost",
        lambda params=None: LogisticRegression(max_iter=300),
    )
    rng = np.random.default_rng(23)
    X = rng.normal(size=(240, 6))
    y = np.tile(np.array([0, 1, 2]), 80)
    timestamps = np.repeat(pd.date_range("2024-08-01", periods=80, freq="D"), 3)

    model = training_module.StackingEnsemble().fit(X, y, timestamps=timestamps)
    probabilities = model.predict_proba(X[-8:])

    assert probabilities.shape == (8, 3)
    assert np.isfinite(probabilities).all()
    np.testing.assert_allclose(probabilities.sum(axis=1), np.ones(8), atol=1e-6)

    artifact_path = tmp_path / "ensemble.pkl"
    joblib.dump({"model": model}, artifact_path)
    reloaded = joblib.load(artifact_path)["model"]
    np.testing.assert_allclose(reloaded.predict_proba(X[-8:]), probabilities)


def test_chronological_folds_keep_simultaneous_matches_together():
    timestamps = np.repeat(pd.date_range("2024-08-01", periods=24, freq="D"), 10)
    splits = training_module._chronological_splits(240, 4, timestamps)
    base_mask, calibration_mask = training_module._chronological_holdout_masks(
        len(timestamps), 50, timestamps
    )

    assert len(splits) == 4
    for train_indices, valid_indices in splits:
        assert timestamps[train_indices].max() < timestamps[valid_indices].min()
    assert timestamps[base_mask].max() < timestamps[calibration_mask].min()


def test_stacking_ensemble_rejects_insufficient_calibration_history(monkeypatch):
    monkeypatch.setattr(training_module, "_make_xgboost", lambda params=None: LogisticRegression())
    monkeypatch.setattr(training_module, "_make_lightgbm", lambda params=None: LogisticRegression())
    monkeypatch.setattr(training_module, "_make_catboost", lambda params=None: LogisticRegression())
    model = training_module.StackingEnsemble()

    with pytest.raises(ValueError, match="90 pre-calibration matches"):
        model.fit(np.zeros((100, 4)), np.tile(np.array([0, 1, 2]), 34)[:100])


def test_calibrator_falls_back_to_valid_input_if_all_class_scores_are_zero(monkeypatch):
    import sklearn.isotonic

    class ZeroIsotonic:
        def __init__(self, out_of_bounds):
            pass

        def fit(self, values, labels):
            return self

        def predict(self, values):
            return np.zeros(len(values))

    monkeypatch.setattr(sklearn.isotonic, "IsotonicRegression", ZeroIsotonic)
    calibrator = training_module._fit_calibrator(
        np.full((3, 3), 1 / 3),
        np.array([0, 1, 2]),
    )
    probabilities = np.array([[0.7, 0.2, 0.1]])

    np.testing.assert_allclose(calibrator.transform(probabilities), probabilities)
