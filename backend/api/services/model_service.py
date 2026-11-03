# api/services/model_service.py
"""Model Service - model registry info and performance metrics."""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ModelService:

    def get_model_info(self, prediction_svc) -> Dict[str, Any]:
        """Return metadata about the currently loaded model."""
        if not prediction_svc.is_loaded:
            return {"status": "not_loaded", "version": None}

        meta = prediction_svc._model_metadata
        return {
            "status": "loaded",
            "version": prediction_svc.model_version,
            "trained_at": meta.get("trained_at"),
            "training_seasons": meta.get("training_seasons", []),
            "n_features": len(prediction_svc._feature_names),
            "feature_names": prediction_svc._feature_names,
            "algorithm": meta.get("algorithm", "ensemble"),
            "cv_evaluation_model": meta.get("cv_evaluation_model"),
            "walk_forward_folds": meta.get("walk_forward_folds"),
            "cv_metrics": meta.get("cv_metrics", {}),
            "baseline_cv_metrics": meta.get("baseline_cv_metrics", {}),
        }

    def get_performance(self, session: Session, model_version: Optional[str] = None) -> Dict[str, Any]:
        """
        Compute prediction accuracy from stored predictions vs actual outcomes.
        Requires a Predictions table - returns empty metrics if not available.
        """
        row = session.execute(text("""
            WITH scored AS (
                SELECT p.*, COALESCE(m.outcome::text, p.actual_outcome) AS result_outcome
                FROM "Predictions" p
                JOIN "Matches" m ON m.id = p.match_id
                WHERE :model_version IS NULL OR p.model_version = :model_version
            )
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE result_outcome IS NOT NULL) AS evaluated,
                COUNT(*) FILTER (WHERE predicted_outcome = result_outcome) AS correct,
                AVG(-LN(GREATEST(CASE result_outcome
                    WHEN 'H' THEN home_win_prob
                    WHEN 'D' THEN draw_prob
                    WHEN 'A' THEN away_win_prob
                END, 0.000001))) FILTER (WHERE result_outcome IS NOT NULL) AS log_loss,
                AVG((
                    POWER(home_win_prob - CASE WHEN result_outcome = 'H' THEN 1 ELSE 0 END, 2) +
                    POWER(draw_prob - CASE WHEN result_outcome = 'D' THEN 1 ELSE 0 END, 2) +
                    POWER(away_win_prob - CASE WHEN result_outcome = 'A' THEN 1 ELSE 0 END, 2)
                ) / 3.0) FILTER (WHERE result_outcome IS NOT NULL) AS brier_score
            FROM scored
        """), {"model_version": model_version}).fetchone()
        if not row or not row.total:
            return {"total_predictions": 0, "evaluated": 0, "accuracy": None, "log_loss": None, "brier_score": None}

        accuracy = row.correct / row.evaluated if row.evaluated else None
        return {
            "total_predictions": int(row.total),
            "evaluated": int(row.evaluated),
            "correct": int(row.correct or 0),
            "accuracy": round(float(accuracy), 4) if accuracy is not None else None,
            "log_loss": round(float(row.log_loss), 4) if row.log_loss is not None else None,
            "brier_score": round(float(row.brier_score), 4) if row.brier_score is not None else None,
        }

