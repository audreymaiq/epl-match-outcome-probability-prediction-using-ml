"""
Evaluation metrics for multi-class football outcome predictions.

Implements proper probabilistic forecast metrics:
- Ranked Probability Score (RPS) - preferred over log-loss for ordered outcomes
- Brier Score per class (OvR)
- Expected Calibration Error (ECE)
- ROI simulation vs naive strategies
- Composite evaluation report

All functions are pure numpy - no sklearn dependencies for core metrics.
"""
from __future__ import annotations

import numpy as np
from typing import Dict, Sequence, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Ranked Probability Score (RPS)
# ─────────────────────────────────────────────────────────────────────────────

def compute_rps(
    y_true: np.ndarray,
    y_proba: np.ndarray,
) -> float:
    """
    Compute mean Ranked Probability Score for 3-class predictions (H/D/A).

    RPS measures the accuracy of ordered probabilistic predictions.
    Lower is better. Perfect probabilistic prediction → RPS = 0.
    Naive (uniform) prediction → RPS ≈ 0.333.

    Formula:
        RPS_i = (1 / (K-1)) * Σ_{k=1}^{K-1} (CDF_pred_k - CDF_actual_k)²

    Args:
        y_true:  Integer class labels (0=H, 1=D, 2=A), shape (n,)
        y_proba: Predicted probabilities, shape (n, 3) - must sum to ~1 per row.

    Returns:
        Mean RPS across all n predictions (scalar).
    """
    n, K = y_proba.shape

    # One-hot encode true labels → cumulative sums
    y_onehot = np.zeros((n, K), dtype=float)
    y_onehot[np.arange(n), y_true] = 1.0

    cum_pred = np.cumsum(y_proba, axis=1)     # (n, K)
    cum_actual = np.cumsum(y_onehot, axis=1)  # (n, K)

    # Sum over K-1 thresholds, average over n
    rps_per_match = np.sum((cum_pred[:, :-1] - cum_actual[:, :-1]) ** 2, axis=1) / (K - 1)
    return float(rps_per_match.mean())


def compute_rps_per_match(
    y_true: np.ndarray,
    y_proba: np.ndarray,
) -> np.ndarray:
    """
    Per-match Ranked Probability Score for post-hoc analysis.

    Returns:
        Array of per-match RPS values, shape (n,).
    """
    n, K = y_proba.shape
    y_onehot = np.zeros((n, K), dtype=float)
    y_onehot[np.arange(n), y_true] = 1.0

    cum_pred = np.cumsum(y_proba, axis=1)
    cum_actual = np.cumsum(y_onehot, axis=1)
    return np.sum((cum_pred[:, :-1] - cum_actual[:, :-1]) ** 2, axis=1) / (K - 1)


# ─────────────────────────────────────────────────────────────────────────────
# Brier Score
# ─────────────────────────────────────────────────────────────────────────────

def compute_brier_score(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    n_classes: int = 3,
) -> Dict[str, float]:
    """
    Multi-class Brier score (MSE over one-hot encoded labels).

    Args:
        y_true:    Integer class labels, shape (n,)
        y_proba:   Predicted probabilities, shape (n, n_classes)
        n_classes: Number of classes (default 3)

    Returns:
        Dict with keys 'overall', 'home_win', 'draw', 'away_win'.
    """
    n = len(y_true)
    y_onehot = np.zeros((n, n_classes), dtype=float)
    y_onehot[np.arange(n), y_true] = 1.0

    squared_errors = (y_proba - y_onehot) ** 2        # (n, K)
    per_class = squared_errors.mean(axis=0)            # (K,)

    class_names = ["home_win", "draw", "away_win"]
    result: Dict[str, float] = {"overall": float(squared_errors.mean())}
    for i, name in enumerate(class_names[:n_classes]):
        result[name] = float(per_class[i])
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Expected Calibration Error (ECE)
# ─────────────────────────────────────────────────────────────────────────────

def compute_ece(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    n_bins: int = 10,
) -> float:
    """
    Expected Calibration Error based on maximum predicted confidence.

    Args:
        y_true:  True class labels, shape (n,)
        y_proba: Predicted probabilities, shape (n, n_classes)
        n_bins:  Number of confidence bins (default 10)

    Returns:
        ECE scalar (lower = better; 0 = perfectly calibrated).
    """
    confidences = y_proba.max(axis=1)
    predictions = y_proba.argmax(axis=1)
    correct = (predictions == y_true).astype(float)

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    n = len(y_true)
    ece = 0.0

    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        mask = (confidences > lo) & (confidences <= hi)
        if mask.sum() == 0:
            continue
        bin_acc = correct[mask].mean()
        bin_conf = confidences[mask].mean()
        ece += (mask.sum() / n) * abs(bin_acc - bin_conf)

    return float(ece)


def compute_calibration_curve(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    n_bins: int = 10,
    class_idx: int = 0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calibration curve data for a single class (OvR).

    Args:
        y_true:    True class labels, shape (n,)
        y_proba:   Predicted probabilities, shape (n, n_classes)
        n_bins:    Number of bins
        class_idx: Class to analyse (0=H, 1=D, 2=A)

    Returns:
        (mean_predicted_prob, fraction_of_positives, bin_counts)
        Each array has shape (n_bins,).
    """
    binary_true = (y_true == class_idx).astype(float)
    class_prob = y_proba[:, class_idx]

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    mean_pred = np.zeros(n_bins)
    frac_pos = np.zeros(n_bins)
    counts = np.zeros(n_bins, dtype=int)

    for i, (lo, hi) in enumerate(zip(bin_edges[:-1], bin_edges[1:])):
        mask = (class_prob > lo) & (class_prob <= hi)
        counts[i] = mask.sum()
        if counts[i] == 0:
            mean_pred[i] = (lo + hi) / 2
            frac_pos[i] = 0.0
        else:
            mean_pred[i] = class_prob[mask].mean()
            frac_pos[i] = binary_true[mask].mean()

    return mean_pred, frac_pos, counts


# ─────────────────────────────────────────────────────────────────────────────
# ROI Simulation
# ─────────────────────────────────────────────────────────────────────────────

def compute_roi_simulation(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    odds: np.ndarray | None = None,
    stake: float = 1.0,
    threshold: float = 0.50,
) -> Dict[str, float]:
    """
    Simulate betting ROI vs naive strategies.

    Strategies:
    1. **Model**:      Bet when model's max probability ≥ threshold.
    2. **Always home**: Bet home win every match.
    3. Baseline accuracy for reference.

    Args:
        y_true:    True labels (0=H, 1=D, 2=A), shape (n,)
        y_proba:   Model probabilities, shape (n, 3)
        odds:      Decimal odds matrix, shape (n, 3).
                   If None, uses empirical frequency implied odds with 10% margin.
        stake:     Bet size per match (currency-neutral)
        threshold: Min probability to place a model bet

    Returns:
        Dict with ROI metrics for each strategy.
    """
    n = len(y_true)

    # Build implied odds from empirical frequencies if not supplied
    if odds is None:
        counts = np.bincount(y_true, minlength=3).astype(float)
        freq = np.clip(counts / n, 0.05, 0.95)
        base_odds = (1.0 / freq) * 0.90   # 10% bookmaker margin
        odds = np.tile(base_odds, (n, 1))

    model_preds = y_proba.argmax(axis=1)
    model_conf = y_proba.max(axis=1)
    bet_mask = model_conf >= threshold

    # ── Strategy 1: Model ──────────────────────────────────────────────────
    model_bets = int(bet_mask.sum())
    model_profit = 0.0
    for i in np.where(bet_mask)[0]:
        pred = model_preds[i]
        if pred == y_true[i]:
            model_profit += stake * (odds[i, pred] - 1.0)
        else:
            model_profit -= stake

    # ── Strategy 2: Always home ────────────────────────────────────────────
    home_profit = 0.0
    for i in range(n):
        if y_true[i] == 0:
            home_profit += stake * (odds[i, 0] - 1.0)
        else:
            home_profit -= stake

    model_roi = (model_profit / (model_bets * stake) * 100) if model_bets > 0 else 0.0
    home_roi = home_profit / (n * stake) * 100

    return {
        "n_matches": n,
        "model_bets": model_bets,
        "model_profit": round(model_profit, 4),
        "model_roi_pct": round(model_roi, 2),
        "home_always_profit": round(home_profit, 4),
        "home_always_roi_pct": round(home_roi, 2),
        "model_accuracy": float((model_preds == y_true).mean()),
        "bet_coverage_pct": round(model_bets / n * 100, 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Composite Report
# ─────────────────────────────────────────────────────────────────────────────

def generate_evaluation_report(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    fold_label: str = "overall",
) -> Dict[str, float]:
    """
    Generate a complete evaluation report suitable for MLflow or JSON logging.

    Includes: accuracy, RPS, ECE, Brier (overall + per class),
              per-class accuracy (home_win / draw / away_win).

    Args:
        y_true:     True labels, shape (n,)
        y_proba:    Predicted probabilities, shape (n, 3)
        fold_label: Label for logging (e.g. 'fold_3', 'overall')

    Returns:
        Flat dict of metric_name → float.
    """
    preds = y_proba.argmax(axis=1)
    report: Dict[str, float] = {
        f"{fold_label}/accuracy": float((preds == y_true).mean()),
        f"{fold_label}/rps": compute_rps(y_true, y_proba),
        f"{fold_label}/ece": compute_ece(y_true, y_proba),
    }

    brier = compute_brier_score(y_true, y_proba)
    for k, v in brier.items():
        report[f"{fold_label}/brier_{k}"] = v

    class_map = {0: "home_win", 1: "draw", 2: "away_win"}
    for cls_idx, cls_name in class_map.items():
        mask = y_true == cls_idx
        if mask.sum() > 0:
            report[f"{fold_label}/accuracy_{cls_name}"] = float((preds[mask] == cls_idx).mean())
            report[f"{fold_label}/support_{cls_name}"] = int(mask.sum())

    return report

