"""Configuration and artifact contracts shared by training and serving."""

import json

import joblib
import numpy as np
import pandas as pd
import pytest

from ml.config import load_ml_config
from ml.inference.predictor import ModelPredictor
from config.competitions import get_competition
from ml.features.contracts import feature_fingerprint


class ConstantModel:
    def predict_proba(self, features):
        return np.tile([0.5, 0.3, 0.2], (len(features), 1))


def test_default_ml_configuration_is_valid():
    config = load_ml_config()
    assert config.cv.min_train_seasons >= 1
    assert config.stacking.min_calibration_matches > 0
    assert set(config.estimators) == {"xgboost", "lightgbm", "catboost"}


def test_external_ml_configuration_overrides_training_parameters(tmp_path):
    config = load_ml_config().as_dict()
    config["cv"]["min_train_seasons"] = 3
    config["estimators"]["lightgbm"]["n_estimators"] = 120
    config["features"]["form_decay"] = 0.7
    config["elo"]["home_advantage"] = 50.0
    path = tmp_path / "experiment.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    loaded = load_ml_config(path)
    assert loaded.cv.min_train_seasons == 3
    assert loaded.estimators["lightgbm"]["n_estimators"] == 120
    assert loaded.elo["home_advantage"] == 50.0
    assert loaded.features.form_decay == 0.7


def test_feature_extractor_uses_training_configuration(tmp_path):
    pytest.importorskip("sqlalchemy")
    from ml.features.feature_extractor import FeatureExtractor

    config = load_ml_config().as_dict()
    config["elo"]["home_advantage"] = 50.0
    path = tmp_path / "feature.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    assert FeatureExtractor(None, config=load_ml_config(path))._elo_config.home_advantage == 50.0


def test_invalid_ml_configuration_fails_before_training(tmp_path):
    config = load_ml_config().as_dict()
    config["stacking"]["calibration_fraction"] = 1.0
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="calibration_fraction"):
        load_ml_config(path)


def test_model_predictor_enforces_feature_order_and_probability_contract(tmp_path):
    path = tmp_path / "model.pkl"
    joblib.dump({
        "schema_version": 2,
        "class_order": ["H", "D", "A"],
        "feature_names": ["elo", "form"],
        "metadata": {"version": "v1", "training_config": load_ml_config().as_dict(),
                     "competition": get_competition().as_dict(), "league": "epl",
                     "feature_config_hash": feature_fingerprint(load_ml_config(), get_competition())},
        "model": ConstantModel(),
    }, path)
    predictor = ModelPredictor(path)
    assert predictor.load()
    values, probabilities = predictor.predict(pd.DataFrame({"form": [2.0], "elo": [1500.0]}))
    np.testing.assert_array_equal(values, [[1500.0, 2.0]])
    np.testing.assert_allclose(probabilities, [0.5, 0.3, 0.2])
    with pytest.raises(ValueError, match="form"):
        predictor.predict(pd.DataFrame({"elo": [1500.0]}))


def test_model_predictor_rejects_artifact_without_feature_configuration(tmp_path):
    path = tmp_path / "old.pkl"
    joblib.dump({
        "schema_version": 2,
        "class_order": ["H", "D", "A"],
        "feature_names": ["elo"],
        "metadata": {"version": "old"},
        "model": ConstantModel(),
    }, path)
    with pytest.raises(ValueError, match="feature configuration"):
        ModelPredictor(path).load()
