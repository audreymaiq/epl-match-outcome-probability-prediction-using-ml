"""Stacking estimator and model factory, independent of API and data collection."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Protocol

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

from ml.config import MLConfig, load_ml_config

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


# ─────────────────────────────────────────────────────────────────────────────
# Model factory (lazy imports - these are optional heavy deps)
# ─────────────────────────────────────────────────────────────────────────────

def _make_xgboost(params: Optional[Dict] = None):
    from xgboost import XGBClassifier
    return XGBClassifier(**(params if params is not None else load_ml_config().estimators["xgboost"]))


def _make_lightgbm(params: Optional[Dict] = None):
    from lightgbm import LGBMClassifier
    return LGBMClassifier(**(params if params is not None else load_ml_config().estimators["lightgbm"]))


def _make_catboost(params: Optional[Dict] = None):
    from catboost import CatBoostClassifier
    return CatBoostClassifier(**(params if params is not None else load_ml_config().estimators["catboost"]))


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
        config: Optional[MLConfig] = None,
    ):
        self._config = config or load_ml_config()
        stack_config = self._config.stacking
        self._preprocessor = _make_preprocessor()
        self._base_learners = [
            ("xgb", _make_xgboost(xgb_params if xgb_params is not None else self._config.estimators["xgboost"])),
            ("lgb", _make_lightgbm(lgb_params if lgb_params is not None else self._config.estimators["lightgbm"])),
            ("cat", _make_catboost(cat_params if cat_params is not None else self._config.estimators["catboost"])),
        ]
        self._meta = LogisticRegression(
            C=stack_config.meta_c, max_iter=stack_config.meta_max_iter,
            solver="lbfgs", random_state=self._config.random_seed,
        )
        self._calibrator: Optional[ProbabilityCalibrator] = None
        self.classes_ = np.array([0, 1, 2])

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sample_weight: Optional[np.ndarray] = None,
        calibration_fraction: Optional[float] = None,
        timestamps: Optional[np.ndarray] = None,
    ) -> "StackingEnsemble":
        """
        Train the full ensemble.

        Reserves the configured latest time window for calibration.
        """
        n = len(X)
        cfg = self._config.stacking
        calibration_fraction = cfg.calibration_fraction if calibration_fraction is None else calibration_fraction
        if not 0 < calibration_fraction < 1:
            raise ValueError("calibration_fraction must be between 0 and 1.")
        if n < cfg.min_base_matches + cfg.min_calibration_matches:
            raise ValueError(
                f"Stacking training needs at least {cfg.min_base_matches} pre-calibration matches "
                f"and {cfg.min_calibration_matches} calibration matches."
            )
        cal_n = max(int(n * calibration_fraction), cfg.min_calibration_matches)
        # Keep the latest timestamps for calibration and never split simultaneous fixtures.
        base_mask, calibration_mask = _chronological_holdout_masks(n, cal_n, timestamps)
        train_end = int(base_mask.sum())
        if train_end < cfg.min_base_matches or int(calibration_mask.sum()) < cfg.min_calibration_matches:
            raise ValueError(
                f"Stacking training needs at least {cfg.min_base_matches} pre-calibration matches "
                f"and {cfg.min_calibration_matches} calibration matches."
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
        n_splits = min(cfg.max_oof_folds, len(X_base) // cfg.min_matches_per_oof_fold - 1, n_time_groups // 2 - 1)
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

