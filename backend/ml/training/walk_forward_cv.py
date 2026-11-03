# ml/training/walk_forward_cv.py
"""Expanding season splits for out of time match outcome evaluation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    log_loss,
    brier_score_loss,
    precision_recall_fscore_support,
    confusion_matrix,
)
from sklearn.base import clone
from ml.models.ensemble import StackingEnsemble

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FoldResult:
    """Results for one walk-forward fold."""
    fold_index: int
    train_size: int
    test_size: int
    train_seasons: List[str]
    test_season: str

    # Core metrics
    accuracy: float
    log_loss: float
    brier_score: float

    # Per-class metrics (Home/Draw/Away)
    precision_per_class: Dict[str, float]
    recall_per_class:    Dict[str, float]
    f1_per_class:        Dict[str, float]
    confusion_matrix:    List[List[int]]

    # Calibration
    expected_calibration_error: float = 0.0

    accuracy_gap_vs_home_always: float = 0.0


@dataclass
class CVResult:
    """Aggregated results across all walk-forward folds."""
    n_folds: int
    folds: List[FoldResult] = field(default_factory=list)

    @property
    def mean_accuracy(self) -> Optional[float]:
        return float(np.mean([f.accuracy for f in self.folds])) if self.folds else None

    @property
    def std_accuracy(self) -> Optional[float]:
        return float(np.std([f.accuracy for f in self.folds])) if self.folds else None

    @property
    def mean_log_loss(self) -> Optional[float]:
        return float(np.mean([f.log_loss for f in self.folds])) if self.folds else None

    @property
    def mean_brier(self) -> Optional[float]:
        return float(np.mean([f.brier_score for f in self.folds])) if self.folds else None

    @property
    def summary(self) -> Dict[str, Any]:
        classes = ["H", "D", "A"]
        if not self.folds:
            summary: Dict[str, Any] = {
                "n_folds": 0,
                "mean_accuracy": None,
                "std_accuracy": None,
                "mean_log_loss": None,
                "mean_brier": None,
            }
            for cls in classes:
                summary[f"precision_{cls}"] = None
                summary[f"recall_{cls}"] = None
                summary[f"f1_{cls}"] = None
            return summary

        per_class = {}
        for cls in classes:
            per_class[f"precision_{cls}"] = float(np.mean([f.precision_per_class.get(cls, 0) for f in self.folds]))
            per_class[f"recall_{cls}"]    = float(np.mean([f.recall_per_class.get(cls, 0) for f in self.folds]))
            per_class[f"f1_{cls}"]        = float(np.mean([f.f1_per_class.get(cls, 0) for f in self.folds]))
        return {
            "n_folds":       self.n_folds,
            "mean_accuracy": round(self.mean_accuracy, 4),
            "std_accuracy":  round(self.std_accuracy, 4),
            "mean_log_loss": round(self.mean_log_loss, 4),
            "mean_brier":    round(self.mean_brier, 4),
            **{k: round(v, 4) for k, v in per_class.items()},
        }


# ─────────────────────────────────────────────────────────────────────────────
# Walk-Forward CV
# ─────────────────────────────────────────────────────────────────────────────

class WalkForwardCV:
    """
    Walk-forward cross-validation for football match outcome prediction.

    Strategy:
      - Sort matches by match_datetime (chronological order is mandatory)
      - Create N folds where each fold tests on the NEXT season
      - Training set is always EXPANDING (all history up to test start)

    Args:
        n_test_seasons: Number of seasons to hold out as test in each fold.
                        Default 1 = predict next season, train on all prior.
        min_train_seasons: Minimum seasons in training set before we trust results.
        gap_rounds: Optional number of opening rounds to exclude from each
                    test season. Defaults to zero so evaluation covers the full season.
    """

    def __init__(
        self,
        n_test_seasons: int = 1,
        min_train_seasons: int = 2,
        gap_rounds: int = 0,
        min_train_matches: int = 100,
        min_test_matches: int = 20,
    ):
        self._n_test = n_test_seasons
        self._min_train = min_train_seasons
        self._gap_rounds = gap_rounds
        self._min_train_matches = min_train_matches
        self._min_test_matches = min_test_matches

    def split(
        self,
        df: pd.DataFrame,
        season_col: str = "season_name",
        date_col: str = "match_datetime",
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Generate (train_indices, test_indices) for each fold.
        Sorted chronologically. Optional gaps exclude opening test rounds.

        Args:
            df:          Full DataFrame with all matches (sorted by date).
            season_col:  Column containing season label (e.g. '2023/24').
            date_col:    Column containing match datetime.

        Returns:
            List of (train_idx, test_idx) pairs.
        """
        df = df.sort_values(date_col).reset_index(drop=True)
        seasons = sorted(df[season_col].unique())

        splits = []
        for i in range(self._min_train, len(seasons) - self._n_test + 1):
            train_seasons = seasons[:i]
            test_seasons  = seasons[i : i + self._n_test]

            train_idx = df[df[season_col].isin(train_seasons)].index.tolist()
            test_idx  = df[
                df[season_col].isin(test_seasons) &
                (df.get("match_week", pd.Series(99, index=df.index)).fillna(99).astype(int) > self._gap_rounds)
            ].index.tolist()

            if len(train_idx) < self._min_train_matches or len(test_idx) < self._min_test_matches:
                continue

            splits.append((np.array(train_idx), np.array(test_idx)))

        logger.info("WalkForwardCV: %d folds generated.", len(splits))
        return splits

    def evaluate(
        self,
        model,
        df: pd.DataFrame,
        feature_cols: List[str],
        target_col: str = "outcome",
        season_col: str = "season_name",
        date_col: str = "match_datetime",
    ) -> CVResult:
        """
        Run walk-forward CV and return aggregated metrics.

        Args:
            model:        Sklearn-compatible model with fit() and predict_proba().
            df:           Full feature DataFrame (all seasons).
            feature_cols: Feature column names.
            target_col:   Target column ('outcome': H/D/A).
            season_col:   Season label column.
            date_col:     Datetime column.

        Returns:
            CVResult with per-fold and aggregate metrics.
        """
        # Encode labels: H=0, D=1, A=2
        label_map = {"H": 0, "D": 1, "A": 2}
        reverse_map = {0: "H", 1: "D", 2: "A"}

        df = df.sort_values(date_col).reset_index(drop=True)
        splits = self.split(df, season_col, date_col)
        seasons = sorted(df[season_col].unique())

        cv_result = CVResult(n_folds=len(splits))

        for fold_i, (train_idx, test_idx) in enumerate(splits):
            X_train = df.loc[train_idx, feature_cols].values.astype(np.float32)
            y_train_raw = df.loc[train_idx, target_col].values
            y_train = np.array([label_map[y] for y in y_train_raw])

            X_test = df.loc[test_idx, feature_cols].values.astype(np.float32)
            y_test_raw = df.loc[test_idx, target_col].values
            y_test = np.array([label_map[y] for y in y_test_raw if y in label_map])

            if len(y_test) == 0:
                continue

            # Filter test idx to only labeled rows
            test_mask = np.array([y in label_map for y in y_test_raw])
            X_test = X_test[test_mask]

            try:
                fold_model = model() if callable(model) and not hasattr(model, "fit") else clone(model)
                if isinstance(fold_model, StackingEnsemble):
                    fold_model.fit(X_train, y_train, timestamps=df.loc[train_idx, date_col].to_numpy())
                else:
                    fold_model.fit(X_train, y_train)
                y_proba = fold_model.predict_proba(X_test)
                y_pred  = np.argmax(y_proba, axis=1)
            except Exception as exc:
                raise RuntimeError(f"Walk forward fold {fold_i} failed") from exc

            # Metrics
            acc    = accuracy_score(y_test, y_pred)
            ll     = log_loss(y_test, y_proba, labels=[0, 1, 2])
            # Brier score: average across all classes
            brier  = float(np.mean([
                brier_score_loss((y_test == c).astype(int), y_proba[:, c])
                for c in range(3)
            ]))

            # Per-class precision/recall/f1
            prec, rec, f1, _ = precision_recall_fscore_support(
                y_test, y_pred, labels=[0, 1, 2], zero_division=0
            )
            cm = confusion_matrix(y_test, y_pred, labels=[0, 1, 2]).tolist()

            # ECE (Expected Calibration Error) - 10 bins
            ece = self._expected_calibration_error(y_test, y_proba)

            # Accuracy gap against a fixed home-win classifier; odds are not available.
            home_acc = np.mean(y_test == 0)
            accuracy_gap = acc - home_acc

            # Determine train/test seasons for this fold
            train_seasons_list = sorted(df.loc[train_idx, season_col].unique().tolist())
            test_season = df.loc[test_idx, season_col].iloc[0] if len(test_idx) > 0 else "unknown"

            fold_result = FoldResult(
                fold_index=fold_i,
                train_size=len(train_idx),
                test_size=len(test_idx),
                train_seasons=train_seasons_list,
                test_season=str(test_season),
                accuracy=round(acc, 4),
                log_loss=round(ll, 4),
                brier_score=round(brier, 4),
                precision_per_class={reverse_map[i]: round(float(prec[i]), 4) for i in range(3)},
                recall_per_class={reverse_map[i]: round(float(rec[i]), 4) for i in range(3)},
                f1_per_class={reverse_map[i]: round(float(f1[i]), 4) for i in range(3)},
                confusion_matrix=cm,
                expected_calibration_error=round(ece, 4),
                accuracy_gap_vs_home_always=round(accuracy_gap, 4),
            )
            cv_result.folds.append(fold_result)

            logger.info(
                "Fold %d | Test: %s | Acc: %.3f | LogLoss: %.3f | Brier: %.3f | "
                "P(Draw): %.3f",
                fold_i, test_season, acc, ll, brier,
                fold_result.precision_per_class.get("D", 0),
            )

        cv_result.n_folds = len(cv_result.folds)
        logger.info("CV Summary: %s", cv_result.summary)
        return cv_result

    @staticmethod
    def _expected_calibration_error(
        y_true: np.ndarray, y_proba: np.ndarray, n_bins: int = 10
    ) -> float:
        """
        Compute multiclass ECE - measures how well predicted probabilities
        match actual frequencies.
        Lower = better calibrated.
        """
        n_classes = y_proba.shape[1]
        ece = 0.0
        for cls in range(n_classes):
            probs_cls = y_proba[:, cls]
            is_cls    = (y_true == cls).astype(float)
            bins = np.linspace(0, 1, n_bins + 1)
            for b in range(n_bins):
                mask = (probs_cls >= bins[b]) & (probs_cls <= bins[b + 1] if b == n_bins - 1 else probs_cls < bins[b + 1])
                if mask.sum() == 0:
                    continue
                avg_conf = probs_cls[mask].mean()
                avg_acc  = is_cls[mask].mean()
                ece += (mask.sum() / len(y_true)) * abs(avg_acc - avg_conf)
        return ece / n_classes


def compute_metrics(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    label_names: List[str] = None,
) -> Dict[str, Any]:
    """
    Standalone metric computation for a single train/test split.
    Returns a dict suitable for MLflow logging.
    """
    if label_names is None:
        label_names = ["H", "D", "A"]

    y_pred = np.argmax(y_proba, axis=1)
    label_map = {name: i for i, name in enumerate(label_names)}

    acc   = accuracy_score(y_true, y_pred)
    ll    = log_loss(y_true, y_proba, labels=list(range(len(label_names))))
    brier = float(np.mean([
        brier_score_loss((y_true == c).astype(int), y_proba[:, c])
        for c in range(len(label_names))
    ]))

    prec, rec, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=list(range(len(label_names))), zero_division=0
    )

    metrics: Dict[str, Any] = {
        "accuracy":   round(acc, 4),
        "log_loss":   round(ll, 4),
        "brier_score": round(brier, 4),
    }
    for i, name in enumerate(label_names):
        metrics[f"precision_{name}"] = round(float(prec[i]), 4)
        metrics[f"recall_{name}"]    = round(float(rec[i]), 4)
        metrics[f"f1_{name}"]        = round(float(f1[i]), 4)
        metrics[f"support_{name}"]   = int(support[i])

    return metrics
