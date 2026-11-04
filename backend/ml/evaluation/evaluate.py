"""Evaluate an artifact on a disjoint dataset strictly after its training period."""

import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss
from ml.data.snapshots import read_dataset
from ml.inference.predictor import ModelPredictor
from ml.models.ensemble import LABEL_MAP
from ml.registry import model_path, verified_manifest


def evaluate(league, version, dataset_id):
    verified_manifest(league, version)
    predictor = ModelPredictor(model_path(league, version))
    predictor.load()
    frame, manifest = read_dataset(league, dataset_id)
    metadata = predictor.metadata
    if manifest["feature_config_hash"] != metadata["feature_config_hash"]:
        raise ValueError("Evaluation dataset uses a different feature configuration")
    if set(frame["match_id"]) & set(metadata["training_match_ids"]):
        raise ValueError("Evaluation data overlaps the model's training matches")
    training, _ = read_dataset(league, metadata["dataset_id"])
    if pd.to_datetime(frame["match_datetime"], utc=True).min() <= pd.to_datetime(training["match_datetime"], utc=True).max():
        raise ValueError("Evaluation data must be strictly later than training data")
    labels = frame["outcome"].map(LABEL_MAP).to_numpy(dtype=int)
    _, probabilities = predictor.predict_batch(frame)
    report = {"league": league, "model_version": version, "dataset_id": dataset_id,
        "rows": len(frame), "accuracy": float(accuracy_score(labels, probabilities.argmax(axis=1))),
        "log_loss": float(log_loss(labels, probabilities, labels=[0, 1, 2])),
        "brier_score": float(np.mean((probabilities-np.eye(3)[labels])**2))}
    # Evaluation output is returned to the caller; artifact directories stay immutable.
    return report
