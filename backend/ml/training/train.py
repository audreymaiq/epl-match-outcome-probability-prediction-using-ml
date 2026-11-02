# ml/training/train.py
"""
Full Training Pipeline - Production-grade EPL Match Outcome Predictor.

Pipeline:
  1. Feature extraction from DB (FeatureExtractor)
  2. Walk-forward cross-validation (WalkForwardCV)
  3. Optional Optuna hyperparameter tuning (per model)
  4. Stacking ensemble (XGBoost + LightGBM + CatBoost → Logistic meta-learner)
  5. Probability calibration on a later held-out window
  6. MLflow experiment tracking
  7. Model serialisation to disk

Model architecture:
  - Base learners: XGBoost, LightGBM, CatBoost (diverse, complementary)
  - Meta-learner: Logistic Regression with L2 (interpretable, calibrated)
  - Calibration: Isotonic regression on held-out calibration set
  - Class weights: optional; no assumed draw weight in the default pipeline
"""

from __future__ import annotations

import logging
import sys
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Protocol

import numpy as np
import pandas as pd
import joblib

from sklearn.linear_model import LogisticRegression
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

from ml.training.walk_forward_cv import WalkForwardCV

logger = logging.getLogger(__name__)


class ProbabilityCalibrator(Protocol):
    def transform(self, probabilities: np.ndarray) -> np.ndarray: ...


class MulticlassCalibrator:
    """Apply fitted one-vs-rest calibrators and normalize the result."""

    def __init__(self, calibrators: List[Any]):
        self._cals = calibrators

    def transform(self, proba: np.ndarray) -> np.ndarray:
        calibrated = np.column_stack([
            calibrator.predict(proba[:, cls])
            for cls, calibrator in enumerate(self._cals)
        ])
        row_sums = calibrated.sum(axis=1, keepdims=True)
        return np.divide(
            calibrated,
            row_sums,
            out=proba.copy(),
            where=row_sums > 1e-9,
        )

# Label encoding
LABEL_MAP     = {"H": 0, "D": 1, "A": 2}
LABEL_REVERSE = {0: "H", 1: "D", 2: "A"}

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


def _chronological_splits(
    n_samples: int,
    n_splits: int,
    timestamps: Optional[np.ndarray] = None,
):
    """Create expanding-window splits without separating simultaneous matches."""
    from sklearn.model_selection import TimeSeriesSplit

    if timestamps is None:
        return list(TimeSeriesSplit(n_splits=n_splits).split(np.arange(n_samples)))
    if len(timestamps) != n_samples:
        raise ValueError("timestamps must contain one value per training sample.")

    sample_times = pd.to_datetime(timestamps, utc=True)
    unique_times = pd.DatetimeIndex(sample_times.unique()).sort_values()
    group_splits = TimeSeriesSplit(n_splits=n_splits).split(unique_times)
    row_splits = []
    for train_groups, valid_groups in group_splits:
        train_mask = sample_times.isin(unique_times[train_groups])
        valid_mask = sample_times.isin(unique_times[valid_groups])
        row_splits.append((np.flatnonzero(train_mask), np.flatnonzero(valid_mask)))
    return row_splits


def _chronological_holdout_masks(
    n_samples: int,
    calibration_size: int,
    timestamps: Optional[np.ndarray] = None,
):
    """Reserve a latest-time calibration set without splitting a kickoff group."""
    if timestamps is None:
        calibration_start = n_samples - calibration_size
        base_mask = np.arange(n_samples) < calibration_start
    else:
        if len(timestamps) != n_samples:
            raise ValueError("timestamps must contain one value per training sample.")
        sample_times = pd.to_datetime(timestamps, utc=True)
        cutoff = np.sort(sample_times.asi8)[n_samples - calibration_size]
        base_mask = sample_times.asi8 < cutoff
    return base_mask, ~base_mask


# ─────────────────────────────────────────────────────────────────────────────
# Optuna tuning (optional)
# ─────────────────────────────────────────────────────────────────────────────

def _tune_xgboost(
    X_train,
    y_train,
    n_trials: int = 30,
    timestamps: Optional[np.ndarray] = None,
) -> Dict:
    """Optuna search for XGBoost hyperparameters."""
    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError:
        logger.warning("Optuna not installed - skipping XGBoost tuning.")
        return {}

    from sklearn.model_selection import cross_val_score
    cv_splits = _chronological_splits(len(X_train), n_splits=3, timestamps=timestamps)

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
        score = cross_val_score(
            model,
            X_train,
            y_train,
            cv=cv_splits,
            scoring="neg_log_loss",
        ).mean()
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
            C=1.0, max_iter=2000, solver="lbfgs", random_state=42,
        )
        self._calibrator: Optional[ProbabilityCalibrator] = None
        self.classes_ = np.array([0, 1, 2])

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sample_weight: Optional[np.ndarray] = None,
        calibration_fraction: float = 0.15,
        timestamps: Optional[np.ndarray] = None,
    ) -> "StackingEnsemble":
        """
        Train the full ensemble.

        Splits data: 85% for base learners + meta, 15% for calibration.
        """
        n = len(X)
        if not 0 < calibration_fraction < 1:
            raise ValueError("calibration_fraction must be between 0 and 1.")
        if n < 140:
            raise ValueError(
                "Stacking training needs at least 90 pre-calibration matches "
                "and 50 calibration matches."
            )
        cal_n = max(int(n * calibration_fraction), 50)
        # Keep the latest timestamps for calibration and never split simultaneous fixtures.
        base_mask, calibration_mask = _chronological_holdout_masks(n, cal_n, timestamps)
        train_end = int(base_mask.sum())
        if train_end < 90 or int(calibration_mask.sum()) < 50:
            raise ValueError(
                "Stacking training needs at least 90 pre-calibration matches "
                "and 50 calibration matches."
            )
        X_base, X_cal = X[base_mask], X[calibration_mask]
        y_base, y_cal = y[base_mask], y[calibration_mask]
        if np.unique(y_base).size != len(self.classes_) or np.unique(y_cal).size != len(self.classes_):
            raise ValueError("Both the base-training and calibration windows must contain H, D, and A outcomes.")
        sw_base = sample_weight[base_mask] if sample_weight is not None else None

        # Build chronological out-of-fold predictions for the meta learner.
        # Each row is predicted by base models that were trained only on earlier rows.
        n_classes = len(self.classes_)
        meta_oof = np.full((len(X_base), len(self._base_learners) * n_classes), np.nan)
        base_timestamps = timestamps[base_mask] if timestamps is not None else None
        n_time_groups = (
            len(pd.to_datetime(base_timestamps, utc=True).unique())
            if base_timestamps is not None
            else len(X_base)
        )
        n_splits = min(5, len(X_base) // 30 - 1, n_time_groups // 2 - 1)
        if n_splits < 2:
            raise ValueError("At least three distinct chronological training windows are required for stacking.")
        splits = _chronological_splits(len(X_base), n_splits, base_timestamps)
        for fold, (fit_idx, valid_idx) in enumerate(splits, start=1):
            fold_preprocessor = _make_preprocessor()
            X_fit = fold_preprocessor.fit_transform(X_base[fit_idx])
            X_valid = fold_preprocessor.transform(X_base[valid_idx])
            y_fit = y_base[fit_idx]
            if np.unique(y_fit).size < n_classes:
                logger.warning("Skipping stacking OOF fold %d: training window lacks an outcome class.", fold)
                continue
            fold_weights = sw_base[fit_idx] if sw_base is not None else None

            fold_predictions = []
            for name, estimator in self._base_learners:
                model = clone(estimator)
                fit_params = {"sample_weight": fold_weights} if fold_weights is not None else {}
                model.fit(X_fit, y_fit, **fit_params)

                fold_proba = model.predict_proba(X_valid)
                aligned = np.zeros((len(valid_idx), n_classes), dtype=float)
                aligned[:, model.classes_.astype(int)] = fold_proba
                fold_predictions.append(aligned)

            meta_oof[valid_idx] = np.hstack(fold_predictions)
            logger.info("Stacking OOF fold %d: %d training, %d validation samples.",
                        fold, len(fit_idx), len(valid_idx))

        oof_mask = np.isfinite(meta_oof).all(axis=1)
        if not oof_mask.any() or np.unique(y_base[oof_mask]).size != n_classes:
            raise ValueError("Chronological out-of-fold samples must cover H, D, and A outcomes.")
        oof_weights = sw_base[oof_mask] if sw_base is not None else None
        self._meta.fit(meta_oof[oof_mask], y_base[oof_mask], sample_weight=oof_weights)

        # Fit final base learners on the complete pre-calibration window.
        X_base_pp = self._preprocessor.fit_transform(X_base)
        X_cal_pp = self._preprocessor.transform(X_cal)
        logger.info("Training final base learners on %d samples...", len(X_base))
        for name, model in self._base_learners:
            fit_params = {"sample_weight": sw_base} if sw_base is not None else {}
            model.fit(X_base_pp, y_base, **fit_params)
            logger.info("  %s trained.", name)

        # Build meta-features on calibration set (out-of-sample)
        meta_cal_X = np.hstack([
            model.predict_proba(X_cal_pp) for _, model in self._base_learners
        ])
        meta_proba_cal = self._meta.predict_proba(meta_cal_X)

        # Calibrate using isotonic regression
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


def _fit_calibrator(proba: np.ndarray, y: np.ndarray) -> ProbabilityCalibrator:
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
    from utils.db_connector import DatabaseConnector
    from utils.logging_config import setup_logging

    setup_logging()
    logger.info("=" * 60)
    logger.info("Training pipeline started | Season: %s | Tune: %s", season_name or "ALL", tune)
    logger.info("=" * 60)

    # ── 1. Feature extraction ─────────────────────────────────────────────
    logger.info("Extracting features from DB...")
    with DatabaseConnector.session_scope() as session:
        from ml.features.feature_extractor import FeatureExtractor
        extractor = FeatureExtractor(session)
        df = extractor.extract_all_finished_matches(season_name=season_name)

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

    # ── 2. Walk-forward CV ────────────────────────────────────────────────
    logger.info("Running walk-forward cross-validation...")
    cv = WalkForwardCV(n_test_seasons=1, min_train_seasons=2, gap_rounds=0)

    # Quick CV with LightGBM (fast) to estimate baseline
    lgb_cv = _make_lightgbm()
    cv_result = cv.evaluate(lgb_cv, df, feature_cols, target_col="outcome")
    logger.info("Walk-forward CV summary: %s", json.dumps(cv_result.summary, indent=2))

    # ── 3. Optional Optuna tuning ─────────────────────────────────────────
    xgb_params, lgb_params, cat_params = {}, {}, {}
    if tune:
        logger.info("Tuning XGBoost (%d trials)...", n_tune_trials)
        xgb_params = _tune_xgboost(
            X,
            y,
            n_trials=n_tune_trials,
            timestamps=df["match_datetime"].to_numpy(),
        )

    # ── 4. Train final ensemble on ALL data ───────────────────────────────
    logger.info("Training final StackingEnsemble on all %d samples...", len(X))
    ensemble = StackingEnsemble(xgb_params, lgb_params, cat_params)
    ensemble.fit(
        X,
        y,
        timestamps=df["match_datetime"].to_numpy(),
    )

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
                "cv_evaluation_model": "LightGBM baseline",
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
    from utils.logging_config import setup_logging

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
    # Invoke the importable module so serialized estimator classes keep a stable
    # module path when this file is launched with ``python -m``.
    from ml.training.train import main as module_main

    sys.exit(module_main())
