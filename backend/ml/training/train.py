"""Evaluate chronologically and train an immutable candidate from a verified dataset."""

import argparse
import json
import os
import platform
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version as package_version
from uuid import uuid4

import numpy as np
from config.competitions import get_competition
from ml.config import load_ml_config
from ml.data.snapshots import create_dataset, read_dataset
from ml.features.contracts import feature_fingerprint
from ml.models.baselines import FrequencyClassifier
from ml.models.ensemble import LABEL_MAP, StackingEnsemble, _make_lightgbm
from ml.registry import save_candidate
from ml.training.walk_forward_cv import WalkForwardCV


def train(season_name=None, save_model=True, model_name=None, mlflow_tracking_uri=None,
          config_path=None, *, league=None, dataset_id=None, seasons=None):
    competition = get_competition(league)
    config = load_ml_config(config_path)
    from ml.provenance import capture_source
    source_files, provenance = capture_source()
    tracking_uri = mlflow_tracking_uri or os.getenv("MLFLOW_TRACKING_URI")
    if tracking_uri:
        try:
            import mlflow
        except ImportError as exc:
            raise ValueError("Install requirements-tracking.txt before enabling MLflow tracking") from exc
    if competition.slug != "epl" and not (config_path or os.getenv("ML_CONFIG_PATH")):
        raise ValueError("Supply an explicit ML configuration for a new competition")
    if dataset_id and (season_name or seasons):
        raise ValueError("A dataset snapshot already defines its training seasons")
    if not dataset_id:
        manifest = create_dataset(league=competition.slug, seasons=seasons or ([season_name] if season_name else None), config_path=config_path)
        dataset_id = manifest["dataset_id"]
    frame, manifest = read_dataset(competition.slug, dataset_id)
    if manifest["feature_config_hash"] != feature_fingerprint(config, competition):
        raise ValueError("Dataset features and requested training configuration are incompatible")
    names = manifest["feature_names"]
    values = frame[names].to_numpy(dtype=np.float32)
    if not np.isfinite(values).all() or not frame["outcome"].isin(LABEL_MAP).all():
        raise ValueError("Dataset contains invalid features or outcome labels")
    labels = frame["outcome"].map(LABEL_MAP).to_numpy(dtype=int)
    cv = WalkForwardCV(n_test_seasons=config.cv.test_seasons, min_train_seasons=config.cv.min_train_seasons,
        gap_rounds=config.cv.gap_rounds, min_train_matches=config.cv.min_train_matches,
        min_test_matches=config.cv.min_test_matches)
    frequency = cv.evaluate(FrequencyClassifier(), frame, names)
    baseline = cv.evaluate(_make_lightgbm(config.estimators["lightgbm"]), frame, names)
    result = cv.evaluate(lambda: StackingEnsemble(config=config), frame, names)
    if not result.folds or len(result.folds) != len(frequency.folds) or len(result.folds) != len(baseline.folds):
        raise ValueError("Insufficient or inconsistent chronological folds; ingest more seasons")
    estimator = StackingEnsemble(config=config)
    estimator.fit(values, labels, timestamps=frame["match_datetime"].to_numpy())
    if capture_source()[1] != provenance:
        raise RuntimeError("Application source changed during training; retry using a stable checkout")
    model_version = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_{uuid4().hex[:12]}"
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True).stdout)
    except (OSError, subprocess.SubprocessError):
        commit, dirty = os.getenv("GIT_COMMIT", "unknown"), None
    metadata = {
        "version": model_version, "league": competition.slug, "competition": competition.as_dict(),
        "feature_config_hash": manifest["feature_config_hash"], "dataset_id": dataset_id,
        "dataset_sha256": manifest["data_sha256"], "training_match_ids": frame["match_id"].tolist(),
        "trained_at": datetime.now(timezone.utc).isoformat(), "training_seasons": manifest["seasons"],
        "n_features": len(names), "n_train_samples": len(frame),
        "algorithm": "StackingEnsemble(XGB+LGB+CatBoost→LR)", "cv_evaluation_model": "StackingEnsemble",
        "walk_forward_folds": len(result.folds), "fold_results": [asdict(fold) for fold in result.folds],
        "cv_metrics": result.summary, "baseline_cv_metrics": baseline.summary,
        "frequency_cv_metrics": frequency.summary, "training_config": config.as_dict(),
        "code_revision": commit, "working_tree_dirty": dirty, "python": platform.python_version(),
        "source_provenance": provenance,
        "libraries": {name: package_version(name) for name in ("numpy", "pandas", "scikit-learn", "xgboost-cpu", "lightgbm", "catboost", "scipy", "joblib")},
        "data_time_policy": manifest["data_time_policy"], "model_name": model_name or config.model_name,
        "history_policy": "prior_local_calendar_day",
    }
    artifact = {"schema_version": 2, "class_order": ["H", "D", "A"], "feature_names": names,
                "model": estimator, "metadata": metadata}
    path = save_candidate(artifact, source_files=source_files) if save_model else None
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
        with mlflow.start_run(run_name=model_version):
            mlflow.log_params({"league": competition.slug, "dataset_id": dataset_id,
                               "feature_config_hash": manifest["feature_config_hash"], "code_revision": commit})
            mlflow.log_metrics({k: v for k, v in result.summary.items() if isinstance(v, (float, int))})
            mlflow.log_dict(metadata, "metadata.json")
            if path:
                mlflow.log_artifact(str(path))
    return {"model_version": model_version, "model_path": str(path) if path else None,
            "dataset_id": dataset_id, "league": competition.slug, "cv_metrics": result.summary,
            "frequency_cv_metrics": frequency.summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league")
    parser.add_argument("--config")
    parser.add_argument("--dataset")
    parser.add_argument("--seasons", nargs="+")
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--mlflow")
    args = parser.parse_args()
    print(json.dumps(train(league=args.league, config_path=args.config, dataset_id=args.dataset,
        seasons=args.seasons, save_model=not args.no_save, mlflow_tracking_uri=args.mlflow)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
