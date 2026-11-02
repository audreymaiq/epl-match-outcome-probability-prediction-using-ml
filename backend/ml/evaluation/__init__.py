"""ML evaluation utilities - metrics, calibration, reliability diagrams."""
from ml.evaluation.metrics import (
    compute_rps,
    compute_rps_per_match,
    compute_brier_score,
    compute_ece,
    compute_calibration_curve,
    compute_roi_simulation,
    generate_evaluation_report,
)
from ml.evaluation.calibration import (
    MulticlassIsotonicCalibrator,
    compute_reliability_data,
)

__all__ = [
    "compute_rps",
    "compute_rps_per_match",
    "compute_brier_score",
    "compute_ece",
    "compute_calibration_curve",
    "compute_roi_simulation",
    "generate_evaluation_report",
    "MulticlassIsotonicCalibrator",
    "compute_reliability_data",
]
