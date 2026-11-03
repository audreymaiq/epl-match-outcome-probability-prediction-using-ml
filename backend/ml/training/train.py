# ml/training/train.py
"""Train and evaluate an EPL outcome model using chronological seasons."""

from __future__ import annotations

import logging
import os
import sys
import argparse
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import numpy as np
import pandas as pd
import joblib

from ml.training.walk_forward_cv import WalkForwardCV
from ml.config import load_ml_config
from ml.models.ensemble import LABEL_MAP, MODELS_DIR, StackingEnsemble, _make_lightgbm

logger = logging.getLogger(__name__)


def train(
    season_name: Optional[str] = None,
    save_model: bool = True,
    model_name: Optional[str] = None,
    mlflow_tracking_uri: Optional[str] = None,
    config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full training pipeline.

    Args:
        season_name:          Limit training data to this season. None = all seasons.
        save_model:           If True, serialise model to disk.
        model_name:           Filename prefix for saved model.
        mlflow_tracking_uri:  MLflow tracking server URI.

    Returns:
        Dict with CV metrics and model path.
    """
    from utils.db_connector import DatabaseConnector
    from utils.logging_config import setup_logging

    setup_logging()
    config = load_ml_config(config_path)
    model_name = model_name or config.model_name
    logger.info("=" * 60)
    logger.info("Training pipeline started | Season: %s", season_name or "ALL")
    logger.info("=" * 60)

    # ── 1. Feature extraction ─────────────────────────────────────────────
    logger.info("Extracting features from DB...")
    with DatabaseConnector.session_scope() as session:
        from ml.features.feature_extractor import FeatureExtractor
        extractor = FeatureExtractor(session, config=config)
        df = extractor.extract_all_finished_matches(season_name=season_name)

    if df.empty:
        raise RuntimeError("No training data found. Run ELT pipeline first.")

    # Drop rows without outcome
    df = df[df["outcome"].notna() & df["outcome"].isin(["H", "D", "A"])].copy()
    df = df.sort_values(["match_datetime", "match_id"]).reset_index(drop=True)
    logger.info("Training set: %d matches after filtering.", len(df))

    # Feature columns (all numeric except identifiers and target)
    exclude = {"match_id", "outcome", "season_name", "match_datetime", "home_team_name", "away_team_name"}
    feature_cols = [
        column for column in df.columns
        if column not in exclude and pd.api.types.is_numeric_dtype(df[column])
    ]
    if not feature_cols:
        raise RuntimeError("Feature extraction produced no numeric model inputs.")
    logger.info("Feature set: %d features.", len(feature_cols))

    # Label encoding
    y = np.array([LABEL_MAP[o] for o in df["outcome"]])
    X = df[feature_cols].values.astype(np.float32)

    # ── 2. Walk-forward CV ────────────────────────────────────────────────
    logger.info("Running walk-forward cross-validation...")
    cv = WalkForwardCV(
        n_test_seasons=config.cv.test_seasons,
        min_train_seasons=config.cv.min_train_seasons,
        gap_rounds=config.cv.gap_rounds,
        min_train_matches=config.cv.min_train_matches,
        min_test_matches=config.cv.min_test_matches,
    )

    # Evaluate the baseline and the actual production estimator on identical folds.
    lgb_cv = _make_lightgbm(config.estimators["lightgbm"])
    baseline_cv = cv.evaluate(lgb_cv, df, feature_cols, target_col="outcome")
    ensemble_cv = cv.evaluate(lambda: StackingEnsemble(config=config), df, feature_cols, target_col="outcome")
    if not baseline_cv.folds or not ensemble_cv.folds:
        raise RuntimeError("Insufficient successful chronological folds to evaluate the model.")
    logger.info("Baseline CV summary: %s", json.dumps(baseline_cv.summary, indent=2))
    logger.info("Ensemble CV summary: %s", json.dumps(ensemble_cv.summary, indent=2))

    # ── 4. Train final ensemble on ALL data ───────────────────────────────
    logger.info("Training final StackingEnsemble on all %d samples...", len(X))
    ensemble = StackingEnsemble(config=config)
    ensemble.fit(
        X,
        y,
        timestamps=df["match_datetime"].to_numpy(),
    )

    # ── 5. Final holdout evaluation (last season) ─────────────────────────
    final_metrics = {}
    if len(ensemble_cv.folds) > 0:
        final_fold = ensemble_cv.folds[-1]
        final_metrics = {
            "cv_accuracy":     ensemble_cv.mean_accuracy,
            "cv_log_loss":     ensemble_cv.mean_log_loss,
            "cv_brier":        ensemble_cv.mean_brier,
            "last_fold_acc":   final_fold.accuracy,
            "last_fold_loss":  final_fold.log_loss,
            "last_test_season": final_fold.test_season,
        }
    logger.info("Final metrics: %s", final_metrics)

    # ── 6. Serialise model ────────────────────────────────────────────────
    model_path = None
    if save_model:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        model_path = MODELS_DIR / f"{model_name}.pkl"
        artifact = {
            "schema_version": 1,
            "class_order": ["H", "D", "A"],
            "model": ensemble,
            "feature_names": feature_cols,
            "metadata": {
                "version": version,
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "training_seasons": sorted(df["season_name"].unique().tolist()) if "season_name" in df.columns else [],
                "n_features": len(feature_cols),
                "n_train_samples": len(X),
                "algorithm": "StackingEnsemble(XGB+LGB+CatBoost→LR)",
                "cv_evaluation_model": "StackingEnsemble",
                "walk_forward_folds": ensemble_cv.n_folds,
                "cv_metrics": ensemble_cv.summary,
                "baseline_cv_metrics": baseline_cv.summary,
                "training_config": config.as_dict(),
            },
        }
        temporary_path = model_path.with_suffix(".pkl.tmp")
        try:
            joblib.dump(artifact, temporary_path, compress=3)
            os.replace(temporary_path, model_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        logger.info("Model saved: %s", model_path)

    # ── 7. MLflow logging ─────────────────────────────────────────────────
    tracking_uri = mlflow_tracking_uri or os.getenv("MLFLOW_TRACKING_URI")
    if tracking_uri:
        try:
            import mlflow
            mlflow.set_tracking_uri(tracking_uri)
            with mlflow.start_run(run_name=f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
                mlflow.log_params({
                    "n_features": len(feature_cols),
                    "n_train_samples": len(X),
                    "season_filter": season_name or "all",
                })
                mlflow.log_metrics({k: v for k, v in final_metrics.items() if isinstance(v, float)})
                if model_path:
                    mlflow.log_artifact(str(model_path))
                logger.info("MLflow run logged.")
        except Exception as exc:
            logger.warning("MLflow logging failed (non-critical): %s", exc)

    return {
        "success": True,
        "model_path": str(model_path) if model_path else None,
        "n_features": len(feature_cols),
        "cv_summary": ensemble_cv.summary,
        "baseline_cv_summary": baseline_cv.summary,
        "metrics": final_metrics,
    }


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> int:
    from utils.logging_config import setup_logging

    parser = argparse.ArgumentParser(
        description="Train EPL Match Outcome Prediction Model",
        epilog='python -m ml.training.train --season "2023/2024"',
    )
    parser.add_argument("--season", default=None, metavar="SEASON")
    parser.add_argument("--no-save", action="store_true", help="Do not save model to disk")
    parser.add_argument("--mlflow", default=None, metavar="URI", help="MLflow tracking URI")
    parser.add_argument("--config", default=None, metavar="PATH", help="Validated JSON ML configuration")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    setup_logging(log_level=args.log_level)

    result = train(
        season_name=args.season,
        save_model=not args.no_save,
        mlflow_tracking_uri=args.mlflow,
        config_path=args.config,
    )

    if result["success"]:
        logger.info("Training complete. Model: %s", result.get("model_path"))
        logger.info("CV Summary: %s", result.get("cv_summary"))
        return 0
    return 1


if __name__ == "__main__":
    # Invoke the importable module so serialized estimator classes keep a stable
    # module path when this file is launched with ``python -m``.
    from ml.training.train import main as module_main

    sys.exit(module_main())
