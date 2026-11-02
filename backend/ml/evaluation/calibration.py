"""
Calibration utilities for multi-class probabilistic football predictions.

Provides:
- MulticlassIsotonicCalibrator: per-class OvR isotonic regression with
  renormalization to ensure probabilities sum to 1 post-calibration.
- compute_reliability_data: reliability diagram data for visualization.

Design notes:
- Uses sklearn's IsotonicRegression per class (stable, monotone, non-parametric)
- After per-class isotonic calibration, rows are L1-renormalized
- Calibrator is serializable (pickle-safe) for model packaging
"""
from __future__ import annotations

import logging
from typing import Dict, List

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import label_binarize

logger = logging.getLogger(__name__)


class MulticlassIsotonicCalibrator:
    """
    Calibrate a multi-class probabilistic classifier using One-vs-Rest
    isotonic regression, then L1-renormalize to ensure rows sum to 1.

    Usage::

        calibrator = MulticlassIsotonicCalibrator(n_classes=3)
        calibrator.fit(y_cal, proba_uncal)       # fit on held-out calibration set
        proba_cal = calibrator.transform(proba_new)

    Attributes:
        n_classes: Number of outcome classes (default 3: H, D, A).
        _calibrators: List of fitted IsotonicRegression, one per class.
        _is_fitted: Whether fit() has been called.
    """

    def __init__(self, n_classes: int = 3) -> None:
        self.n_classes = n_classes
        self._calibrators: List[IsotonicRegression] = []
        self._is_fitted: bool = False

    # ── Public API ─────────────────────────────────────────────────────────

    def fit(self, y_true: np.ndarray, y_proba: np.ndarray) -> "MulticlassIsotonicCalibrator":
        """
        Fit one IsotonicRegression per class on a held-out calibration set.

        Args:
            y_true:  True integer labels, shape (n,).
            y_proba: Uncalibrated probabilities, shape (n, n_classes).

        Returns:
            self (for chaining)
        """
        n_samples = len(y_true)
        if n_samples < 20:
            logger.warning(
                "Calibration set has only %d samples - isotonic calibration may overfit.", n_samples
            )

        classes = list(range(self.n_classes))
        y_bin = label_binarize(y_true, classes=classes)  # (n, K)
        # label_binarize returns (n,1) for binary - handle gracefully
        if y_bin.shape[1] == 1:
            y_bin = np.hstack([1 - y_bin, y_bin])

        self._calibrators = []
        for cls_idx in range(self.n_classes):
            ir = IsotonicRegression(out_of_bounds="clip", increasing=True)
            ir.fit(y_proba[:, cls_idx], y_bin[:, cls_idx])
            self._calibrators.append(ir)
            logger.debug("Fitted calibrator for class %d on %d samples.", cls_idx, n_samples)

        self._is_fitted = True
        return self

    def transform(self, y_proba: np.ndarray) -> np.ndarray:
        """
        Apply calibration and L1-renormalize each row.

        Args:
            y_proba: Uncalibrated probabilities, shape (n, n_classes).

        Returns:
            Calibrated, normalized probabilities, shape (n, n_classes).

        Raises:
            RuntimeError: If fit() has not been called.
        """
        if not self._is_fitted:
            raise RuntimeError("MulticlassIsotonicCalibrator: call fit() before transform().")

        calibrated = np.zeros_like(y_proba, dtype=float)
        for cls_idx, ir in enumerate(self._calibrators):
            calibrated[:, cls_idx] = ir.predict(y_proba[:, cls_idx])

        # L1-renormalize: isotonic breaks the simplex constraint
        row_sums = calibrated.sum(axis=1, keepdims=True)
        row_sums = np.where(row_sums <= 0, 1.0, row_sums)
        calibrated = calibrated / row_sums

        # Clip to [eps, 1] and renorm again for numerical safety
        eps = 1e-6
        calibrated = np.clip(calibrated, eps, 1.0 - eps)
        calibrated = calibrated / calibrated.sum(axis=1, keepdims=True)

        return calibrated

    def fit_transform(self, y_true: np.ndarray, y_proba: np.ndarray) -> np.ndarray:
        """Fit and transform in one step (convenience method)."""
        return self.fit(y_true, y_proba).transform(y_proba)

    @property
    def is_fitted(self) -> bool:
        """True if fit() has been called successfully."""
        return self._is_fitted

    def __repr__(self) -> str:
        status = "fitted" if self._is_fitted else "unfitted"
        return f"MulticlassIsotonicCalibrator(n_classes={self.n_classes}, status={status})"


# ─────────────────────────────────────────────────────────────────────────────
# Reliability Diagram Data
# ─────────────────────────────────────────────────────────────────────────────

def compute_reliability_data(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    class_idx: int = 0,
    n_bins: int = 10,
) -> Dict:
    """
    Compute data for a reliability (calibration) diagram for a single class.

    Args:
        y_true:    True class labels, shape (n,)
        y_proba:   Predicted probabilities, shape (n, n_classes)
        class_idx: Class to plot (0=home_win, 1=draw, 2=away_win)
        n_bins:    Number of probability bins

    Returns:
        Dict with keys:
        - 'class': class name string
        - 'mean_predicted': list of bin mean predicted probabilities
        - 'fraction_of_positives': list of empirical positive rates
        - 'counts': list of sample counts per bin
        - 'ece_class': float ECE for this class only
        - 'perfect_calibration': [0, 1] for reference line
    """
    from ml.evaluation.metrics import compute_calibration_curve

    mean_pred, frac_pos, counts = compute_calibration_curve(
        y_true, y_proba, n_bins=n_bins, class_idx=class_idx
    )

    # Class-specific ECE
    binary_true = (y_true == class_idx).astype(float)
    class_prob = y_proba[:, class_idx]
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    n = len(y_true)
    ece_class = 0.0
    for i, (lo, hi) in enumerate(zip(bin_edges[:-1], bin_edges[1:])):
        mask = (class_prob > lo) & (class_prob <= hi)
        if mask.sum() == 0:
            continue
        ece_class += (mask.sum() / n) * abs(frac_pos[i] - mean_pred[i])

    class_names = {0: "home_win", 1: "draw", 2: "away_win"}
    return {
        "class": class_names.get(class_idx, str(class_idx)),
        "mean_predicted": mean_pred.tolist(),
        "fraction_of_positives": frac_pos.tolist(),
        "counts": counts.tolist(),
        "ece_class": round(float(ece_class), 6),
        "perfect_calibration": [0.0, 1.0],
    }

