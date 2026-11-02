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
            "walk_forward_folds": meta.get("walk_forward_folds"),
            "cv_metrics": meta.get("cv_metrics", {}),
        }

    def get_performance(self, session: Session) -> Dict[str, Any]:
        """
        Compute prediction accuracy from stored predictions vs actual outcomes.
        Requires a Predictions table - returns empty metrics if not available.
        """
        try:
            row = session.execute(text("""
                SELECT
                    COUNT(*)                                                          AS total,
                    SUM(CASE WHEN predicted_outcome = actual_outcome THEN 1 ELSE 0 END) AS correct,
                    SUM(CASE WHEN actual_outcome IS NOT NULL THEN 1 ELSE 0 END)       AS evaluated
                FROM "Predictions"
            """)).fetchone()

            if not row or not row.total:
                return {"total_predictions": 0, "evaluated": 0, "accuracy": None}

            accuracy = row.correct / row.evaluated if row.evaluated else None
            return {
                "total_predictions": int(row.total),
                "evaluated": int(row.evaluated),
                "correct": int(row.correct or 0),
                "accuracy": round(float(accuracy), 4) if accuracy else None,
            }
        except Exception as exc:
            logger.warning("Performance query failed (table may not exist yet): %s", exc)
            return {"total_predictions": 0, "evaluated": 0, "accuracy": None, "note": str(exc)}

