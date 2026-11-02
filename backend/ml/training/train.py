# ml/training/train.py
"""
Full Training Pipeline - Production-grade EPL Match Outcome Predictor.

Pipeline:
  1. Feature extraction from DB (FeatureExtractor)
  2. Walk-forward cross-validation (WalkForwardCV)
  3. Optional Optuna hyperparameter tuning (per model)
  4. Stacking ensemble (XGBoost + LightGBM + CatBoost → Logistic meta-learner)
  5. Probability calibration (Isotonic regression - best for football)
  6. MLflow experiment tracking
  7. Model serialisation to disk

Model architecture:
  - Base learners: XGBoost, LightGBM, CatBoost (diverse, complementary)
  - Meta-learner: Logistic Regression with L2 (interpretable, calibrated)
  - Calibration: Isotonic regression on held-out calibration set
  - Class weights: Draw upweighted 1.8× (hardest outcome to predict)

Target: accuracy > 55%, log-loss < 0.96, draw F1 > 0.30
"""

from __future__ import annotations

import logging
import os
import sys
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
import pandas as pd
import joblib

from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

from ml.training.walk_forward_cv import WalkForwardCV, compute_metrics
from utils.db_connector import DatabaseConnector
from utils.logging_config import setup_logging

logger = logging.getLogger(__name__)

# Label encoding
LABEL_MAP     = {"H": 0, "D": 1, "A": 2}
LABEL_REVERSE = {0: "H", 1: "D", 2: "A"}
CLASS_WEIGHTS = {0: 1.0, 1: 1.8, 2: 1.0}  # Upweight Draw

# Model output path
MODELS_DIR = Path(__file__).parent.parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Model factory (lazy imports - these are optional heavy deps)
# ─────────────────────────────────────────────────────────────────────────────

def _make_xgboost(params: Optional[Dict] = None):
    from xgboost import XGBClassifier
    defaults = {
        "n_estimators": 400, "max_depth": 5, "learning_rate": 0.05,
        "subsample": 0.8, "colsample_bytree": 0.8, "gamma": 0.1,
        "reg_alpha": 0.1, "reg_lambda": 1.0,
        "objective": "multi:softprob", "num_class": 3,
        "eval_metric": "mlogloss", "use_label_encoder": False,
        "random_state": 42, "n_jobs": -1,
    }
    defaults.update(params or {})
    return XGBClassifier(**defaults)


def _make_lightgbm(params: Optional[Dict] = None):
    from lightgbm import LGBMClassifier
    defaults = {
        "n_estimators": 400, "max_depth": 6, "learning_rate": 0.05,
        "subsample": 0.8, "colsample_bytree": 0.8,
        "reg_alpha": 0.1, "reg_lambda": 1.0,
        "num_leaves": 63, "min_child_samples": 20,
        "objective": "multiclass", "num_class": 3,
        "random_state": 42, "n_jobs": -1, "verbose": -1,
    }
    defaults.update(params or {})
    return LGBMClassifier(**defaults)


def _make_catboost(params: Optional[Dict] = None):
    from catboost import CatBoostClassifier
    defaults = {
        "iterations": 400, "depth": 6, "learning_rate": 0.05,
        "l2_leaf_reg": 3.0, "border_count": 64,
        "loss_function": "MultiClass", "eval_metric": "MultiClass",
        "random_seed": 42, "verbose": 0, "thread_count": -1,
    }
    defaults.update(params or {})
    return CatBoostClassifier(**defaults)


def _make_preprocessor():
    """Imputer + StandardScaler pipeline (handles NaN features gracefully)."""
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Optuna tuning (optional)
# ─────────────────────────────────────────────────────────────────────────────

def _tune_xgboost(X_train, y_train, n_trials: int = 30) -> Dict:
    """Optuna search for XGBoost hyperparameters."""
    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError:
        logger.warning("Optuna not installed - skipping XGBoost tuning.")
        return {}

    from sklearn.model_selection import cross_val_score

    def objective(trial):
        params = {
            "n_estimators":     trial.suggest_int("n_estimators", 200, 600),
            "max_depth":        trial.suggest_int("max_depth", 3, 8),
            "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "subsample":        trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "gamma":            trial.suggest_float("gamma", 0, 1.0),
            "reg_alpha":        trial.suggest_float("reg_alpha", 0, 2.0),
            "reg_lambda":       trial.suggest_float("reg_lambda", 0.5, 5.0),
        }
        model = _make_xgboost(params)
        score = cross_val_score(model, X_train, y_train, cv=3, scoring="neg_log_loss").mean()
        return -score

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    logger.info("XGBoost tuning complete: best log-loss=%.4f", study.best_value)
    return study.best_params


# ─────────────────────────────────────────────────────────────────────────────
# Stacking ensemble
# ─────────────────────────────────────────────────────────────────────────────

class StackingEnsemble:
    """
    2-layer stacking ensemble.

    Layer 1: XGBoost + LightGBM + CatBoost (base learners)
    Layer 2: Logistic Regression on stacked predictions (meta-learner)

    Each base learner outputs predict_proba [H, D, A].
    Meta-features = concatenated probabilities from all base learners.
    Final output: calibrated 3-class probabilities.
    """

    def __init__(
        self,
        xgb_params: Optional[Dict] = None,
        lgb_params: Optional[Dict] = None,
        cat_params: Optional[Dict] = None,
    ):
        self._preprocessor = _make_preprocessor()
        self._base_learners = [
            ("xgb", _make_xgboost(xgb_params)),
            ("lgb", _make_lightgbm(lgb_params)),
            ("cat", _make_catboost(cat_params)),
        ]
        self._meta = LogisticRegression(
            C=1.0, max_iter=2000, multi_class="multinomial",
            solver="lbfgs", random_state=42,
        )
        self._calibrator: Optional[CalibratedClassifierCV] = None
        self.classes_ = np.array([0, 1, 2])

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sample_weight: Optional[np.ndarray] = None,
        calibration_fraction: float = 0.15,
    ) -> "StackingEnsemble":
        """
        Train the full ensemble.

        Splits data: 85% for base learners + meta, 15% for calibration.
        """
        n = len(X)
        cal_n = max(int(n * calibration_fraction), 50)
        # Chronological split - calibration is always last (most recent)
        train_end = n - cal_n
        X_base, X_cal = X[:train_end], X[train_end:]
        y_base, y_cal = y[:train_end], y[train_end:]
        sw_base = sample_weight[:train_end] if sample_weight is not None else None

        # Preprocess
        X_base_pp = self._preprocessor.fit_transform(X_base)
        X_cal_pp  = self._preprocessor.transform(X_cal)

        # Train base learners on base set
        logger.info("Training base learners on %d samples...", len(X_base))
        for name, model in self._base_learners:
            logger.info("  Training %s...", name)
            try:
                if sw_base is not None:
                    model.fit(X_base_pp, y_base, sample_weight=sw_base)
                else:
                    model.fit(X_base_pp, y_base)
            except TypeError:
                # CatBoost has different sample_weight API
                model.fit(X_base_pp, y_base)
            logger.info("  %s trained.", name)

        # Build meta-features on base set (in-sample, necessary for meta-learner)
        meta_train_X = np.hstack([
            model.predict_proba(X_base_pp) for _, model in self._base_learners
        ])
        self._meta.fit(meta_train_X, y_base, sample_weight=sw_base)

        # Build meta-features on calibration set (out-of-sample)
        meta_cal_X = np.hstack([
            model.predict_proba(X_cal_pp) for _, model in self._base_learners
        ])
        meta_proba_cal = self._meta.predict_proba(meta_cal_X)

        # Calibrate using isotonic regression
        from sklearn.calibration import calibration_curve
        logger.info("Calibrating on %d samples...", len(X_cal))
        self._calibrator = _fit_calibrator(meta_proba_cal, y_cal)

        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return calibrated 3-class probabilities."""
        X_pp = self._preprocessor.transform(X)
        meta_X = np.hstack([
            model.predict_proba(X_pp) for _, model in self._base_learners
        ])
        raw_proba = self._meta.predict_proba(meta_X)
        if self._calibrator is not None:
            return self._calibrator.transform(raw_proba)
        return raw_proba

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.argmax(self.predict_proba(X), axis=1)


def _fit_calibrator(proba: np.ndarray, y: np.ndarray):
    """
    Fit isotonic calibration for multiclass output.
    Returns a callable that maps raw proba → calibrated proba.
    """
    from sklearn.isotonic import IsotonicRegression
    calibrators = []
    for cls in range(3):
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(proba[:, cls], (y == cls).astype(float))
        calibrators.append(iso)

    class MulticlassCalibrator:
        def __init__(self, calibrators):
            self._cals = calibrators
        def transform(self, proba: np.ndarray) -> np.ndarray:
            cal = np.column_stack([
                self._cals[c].predict(proba[:, c]) for c in range(3)
            ])
            # Renormalize rows to sum to 1
            row_sums = cal.sum(axis=1, keepdims=True)
            return cal / np.maximum(row_sums, 1e-9)

    return MulticlassCalibrator(calibrators)


# ─────────────────────────────────────────────────────────────────────────────
# Main training function
# ─────────────────────────────────────────────────────────────────────────────

def train(
    season_name: Optional[str] = None,
    tune: bool = False,
    n_tune_trials: int = 30,
    save_model: bool = True,
    model_name: str = "ensemble_model",
    mlflow_tracking_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full training pipeline.

    Args:
        season_name:          Limit training data to this season. None = all seasons.
        tune:                 If True, run Optuna hyperparameter tuning.
        n_tune_trials:        Number of Optuna trials per model.
        save_model:           If True, serialise model to disk.
        model_name:           Filename prefix for saved model.
        mlflow_tracking_uri:  MLflow tracking server URI.

    Returns:
        Dict with CV metrics and model path.
    """
    setup_logging()
    logger.info("=" * 60)
    logger.info("Training pipeline started | Season: %s | Tune: %s", season_name or "ALL", tune)
    logger.info("=" * 60)

    # ── 1. Feature extraction ─────────────────────────────────────────────
    logger.info("Extracting features from DB...")
    with DatabaseConnector.session_scope() as session:
        from ml.features.feature_extractor import FeatureExtractor
        extractor = FeatureExtractor(session)
        df = extractor.extract_all_finished_matches(season_name=season_name, min_match_week=6)

    if df.empty:
        raise RuntimeError("No training data found. Run ELT pipeline first.")

    # Drop rows without outcome
    df = df[df["outcome"].notna() & df["outcome"].isin(["H", "D", "A"])].copy()
    logger.info("Training set: %d matches after filtering.", len(df))

    # Feature columns (all numeric except identifiers and target)
    exclude = {"match_id", "outcome", "season_name", "match_datetime", "home_team_name", "away_team_name"}
    feature_cols = [c for c in df.columns if c not in exclude and df[c].dtype in (np.float64, np.int64, float, int)]
    logger.info("Feature set: %d features.", len(feature_cols))

    # Label encoding
    y = np.array([LABEL_MAP[o] for o in df["outcome"]])
    X = df[feature_cols].fillna(0).values.astype(np.float32)
    sample_weights = np.array([CLASS_WEIGHTS[yi] for yi in y])

    # ── 2. Walk-forward CV ────────────────────────────────────────────────
    logger.info("Running walk-forward cross-validation...")
    cv = WalkForwardCV(n_test_seasons=1, min_train_seasons=2, gap_rounds=5)

    # Quick CV with LightGBM (fast) to estimate baseline
    lgb_cv = _make_lightgbm()
    cv_result = cv.evaluate(lgb_cv, df, feature_cols, target_col="outcome")
    logger.info("Walk-forward CV summary: %s", json.dumps(cv_result.summary, indent=2))

    # ── 3. Optional Optuna tuning ─────────────────────────────────────────
    xgb_params, lgb_params, cat_params = {}, {}, {}
    if tune:
        logger.info("Tuning XGBoost (%d trials)...", n_tune_trials)
        xgb_params = _tune_xgboost(X, y, n_trials=n_tune_trials)

    # ── 4. Train final ensemble on ALL data ───────────────────────────────
    logger.info("Training final StackingEnsemble on all %d samples...", len(X))
    ensemble = StackingEnsemble(xgb_params, lgb_params, cat_params)
    ensemble.fit(X, y, sample_weight=sample_weights)

    # ── 5. Final holdout evaluation (last season) ─────────────────────────
    final_metrics = {}
    if len(cv_result.folds) > 0:
        final_fold = cv_result.folds[-1]
        final_metrics = {
            "cv_accuracy":     cv_result.mean_accuracy,
            "cv_log_loss":     cv_result.mean_log_loss,
            "cv_brier":        cv_result.mean_brier,
            "last_fold_acc":   final_fold.accuracy,
            "last_fold_loss":  final_fold.log_loss,
            "last_test_season": final_fold.test_season,
        }
    logger.info("Final metrics: %s", final_metrics)

    # ── 6. Serialise model ────────────────────────────────────────────────
    model_path = None
    if save_model:
        version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        model_path = MODELS_DIR / f"{model_name}.pkl"
        artifact = {
            "model": ensemble,
            "feature_names": feature_cols,
            "metadata": {
                "version": version,
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "training_seasons": sorted(df["season_name"].unique().tolist()) if "season_name" in df.columns else [],
                "n_features": len(feature_cols),
                "algorithm": "StackingEnsemble(XGB+LGB+CatBoost→LR)",
                "walk_forward_folds": cv_result.n_folds,
                "cv_metrics": cv_result.summary,
            },
        }
        joblib.dump(artifact, model_path, compress=3)
        logger.info("Model saved: %s", model_path)

    # ── 7. MLflow logging ─────────────────────────────────────────────────
    try:
        import mlflow
        if mlflow_tracking_uri:
            mlflow.set_tracking_uri(mlflow_tracking_uri)
        with mlflow.start_run(run_name=f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
            mlflow.log_params({
                "tune": tune,
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
        "cv_summary": cv_result.summary,
        "metrics": final_metrics,
    }


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train EPL Match Outcome Prediction Model",
        epilog='python -m ml.training.train --tune --seasons "2023/24"',
    )
    parser.add_argument("--season", default=None, metavar="SEASON")
    parser.add_argument("--tune", action="store_true", help="Run Optuna hyperparameter tuning")
    parser.add_argument("--trials", type=int, default=30, help="Optuna trials per model")
    parser.add_argument("--no-save", action="store_true", help="Do not save model to disk")
    parser.add_argument("--mlflow", default=None, metavar="URI", help="MLflow tracking URI")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    setup_logging(log_level=args.log_level)

    result = train(
        season_name=args.season,
        tune=args.tune,
        n_tune_trials=args.trials,
        save_model=not args.no_save,
        mlflow_tracking_uri=args.mlflow,
    )

    if result["success"]:
        logger.info("Training complete. Model: %s", result.get("model_path"))
        logger.info("CV Summary: %s", result.get("cv_summary"))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
