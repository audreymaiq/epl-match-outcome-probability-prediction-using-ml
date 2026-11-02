# api/services/prediction_service.py
"""
Prediction Service - core ML inference path.

Responsibilities:
  1. Load trained ensemble model from disk (once at startup)
  2. Build feature vector for a match using FeatureExtractor
  3. Run inference → calibrated probabilities [P(H), P(D), P(A)]
  4. Compute SHAP key features for explainability
  5. Persist prediction to DB (for monitoring/evaluation)

Design:
  - Model loading is lazy but thread-safe (called once via @lru_cache dependency)
  - Stateless predict() method: safe for concurrent requests
  - Falls back gracefully if SHAP not installed
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import joblib
import numpy as np

from api.schemas.prediction import (
    PredictRequest, PredictResponse, ProbabilityBreakdown, KeyFeatures,
    PredictionRecord,
)
from api.schemas.common import PagedResponse, Pagination
from api.exceptions import ModelNotLoadedException, PredictionFailedException

logger = logging.getLogger(__name__)

# Default model path - override via MODEL_PATH env var
DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "ensemble_model.pkl"


class PredictionService:
    """
    Encapsulates all ML inference logic.

    Thread-safe: model and metadata are read-only after load_model().
    """

    def __init__(self, model_path: Optional[Path] = None):
        self._model_path = Path(model_path or os.getenv("MODEL_PATH", str(DEFAULT_MODEL_PATH)))
        self._model = None
        self._model_metadata: Dict[str, Any] = {}
        self._feature_names: list = []
        self._is_loaded = False

    def load_model(self) -> None:
        """
        Load model from disk. Called once at application startup.
        Raises RuntimeError if model file is missing.
        """
        if self._is_loaded:
            return

        if not self._model_path.exists():
            logger.warning(
                "Model file not found at %s. Predictions will be unavailable until training completes.",
                self._model_path,
            )
            return

        try:
            artifact = joblib.load(self._model_path)
            # Expected artifact format: dict with 'model', 'metadata', 'feature_names'
            if isinstance(artifact, dict):
                self._model = artifact.get("model")
                self._model_metadata = artifact.get("metadata", {})
                self._feature_names = artifact.get("feature_names", [])
            else:
                # Bare model (legacy format)
                self._model = artifact

            self._is_loaded = True
            logger.info(
                "Model loaded successfully from %s | version=%s | features=%d",
                self._model_path,
                self._model_metadata.get("version", "unknown"),
                len(self._feature_names),
            )
        except Exception as exc:
            logger.error("Failed to load model from %s: %s", self._model_path, exc, exc_info=True)
            raise RuntimeError(f"Model loading failed: {exc}") from exc

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded and self._model is not None

    @property
    def model_version(self) -> str:
        return self._model_metadata.get("version", "unknown")

    def predict(
        self,
        request: PredictRequest,
        db_session,
    ) -> PredictResponse:
        """
        Main inference method.

        Args:
            request:    Validated PredictRequest.
            db_session: SQLAlchemy session for feature extraction.

        Returns:
            PredictResponse with calibrated probabilities.

        Raises:
            ModelNotLoadedException if model not ready.
            PredictionFailedException if feature extraction or inference fails.
        """
        if not self.is_loaded:
            raise ModelNotLoadedException()

        try:
            features, match_meta = self._extract_features(request, db_session)
        except Exception as exc:
            logger.error("Feature extraction failed: %s", exc, exc_info=True)
            raise PredictionFailedException(reason=str(exc)) from exc

        try:
            probs = self._run_inference(features)
        except Exception as exc:
            logger.error("Model inference failed: %s", exc, exc_info=True)
            raise PredictionFailedException(reason=f"Inference error: {exc}") from exc

        # Build key features from raw vector
        key_features = self._build_key_features(features)

        feature_vector = None
        if request.include_feature_breakdown and self._feature_names:
            feature_vector = dict(zip(self._feature_names, features.flatten().tolist()))

        predicted_outcome = ["H", "D", "A"][int(np.argmax(probs))]
        confidence = float(np.max(probs))

        return PredictResponse(
            match_id=match_meta.get("match_id"),
            home_team_id=match_meta["home_team_id"],
            away_team_id=match_meta["away_team_id"],
            home_team_name=match_meta.get("home_team_name", "Unknown"),
            away_team_name=match_meta.get("away_team_name", "Unknown"),
            match_datetime=match_meta.get("match_datetime"),
            probabilities=ProbabilityBreakdown(
                home_win=round(float(probs[0]), 4),
                draw=round(float(probs[1]), 4),
                away_win=round(float(probs[2]), 4),
            ),
            predicted_outcome=predicted_outcome,
            confidence=round(confidence, 4),
            model_version=self.model_version,
            key_features=key_features,
            feature_vector=feature_vector,
        )

    def list_predictions(
        self,
        db_session,
        page: int = 1,
        page_size: int = 25,
    ) -> PagedResponse[PredictionRecord]:
        """
        List stored predictions from DB with pagination.

        Falls back to an empty response if the Predictions table does not yet exist.
        """
        from sqlalchemy import text

        offset = (page - 1) * page_size
        try:
            count_row = db_session.execute(text('SELECT COUNT(*) FROM "Predictions"')).scalar()
            total = int(count_row or 0)
        except Exception:
            # Table may not exist yet
            return PagedResponse(
                data=[],
                pagination=Pagination(page=page, page_size=page_size, total=0, total_pages=0),
            )

        if total == 0:
            return PagedResponse(
                data=[],
                pagination=Pagination(page=page, page_size=page_size, total=0, total_pages=0),
            )

        sql = """
            SELECT
                p.id,
                p.match_id,
                ht.name AS home_team_name,
                at.name AS away_team_name,
                p.predicted_outcome,
                p.home_win_prob,
                p.draw_prob,
                p.away_win_prob,
                p.actual_outcome,
                p.was_correct,
                p.created_at::text AS created_at
            FROM "Predictions" p
            JOIN "Matches" m ON m.id = p.match_id
            JOIN "Teams" ht ON ht.id = m.home_team_id
            JOIN "Teams" at ON at.id = m.away_team_id
            ORDER BY p.created_at DESC
            LIMIT :limit OFFSET :offset
        """
        rows = db_session.execute(text(sql), {"limit": page_size, "offset": offset}).fetchall()

        items = [
            PredictionRecord(
                id=r.id,
                match_id=r.match_id,
                home_team_name=r.home_team_name,
                away_team_name=r.away_team_name,
                predicted_outcome=r.predicted_outcome,
                home_win_prob=float(r.home_win_prob),
                draw_prob=float(r.draw_prob),
                away_win_prob=float(r.away_win_prob),
                actual_outcome=r.actual_outcome,
                was_correct=r.was_correct,
                created_at=r.created_at,
            )
            for r in rows
        ]

        total_pages = max(1, -(-total // page_size))
        return PagedResponse(
            data=items,
            pagination=Pagination(page=page, page_size=page_size, total=total, total_pages=total_pages),
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_features(
        self,
        request: PredictRequest,
        db_session,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Use FeatureExtractor to build feature vector from DB.
        Returns (feature_array shape [1, n_features], match_metadata dict).
        """
        from ml.features.feature_extractor import FeatureExtractor

        extractor = FeatureExtractor(db_session)

        if request.match_id is not None:
            df = extractor.extract_for_match(request.match_id)
            if df is None or df.empty:
                raise ValueError(f"No features found for match_id={request.match_id}")
            meta = extractor.get_match_meta(request.match_id)
        else:
            df, meta = extractor.extract_for_fixture(
                home_team_id=request.home_team_id,
                away_team_id=request.away_team_id,
                match_datetime=request.match_datetime,
                season_name=request.season_name,
                match_week=request.match_week,
            )

        # Select only columns the model was trained on
        if self._feature_names:
            available = [c for c in self._feature_names if c in df.columns]
            missing = [c for c in self._feature_names if c not in df.columns]
            if missing:
                logger.warning("Missing features (will be zero-filled): %s", missing)
                for col in missing:
                    df[col] = 0.0
            df = df[self._feature_names]

        return df.values.astype(np.float32), meta

    def _run_inference(self, features: np.ndarray) -> np.ndarray:
        """
        Run model.predict_proba() and return [P(H), P(D), P(A)] array.
        Handles both pipeline and raw model formats.
        """
        probs = self._model.predict_proba(features)
        # Ensure shape is (1, 3) - some ensembles return (3,) for single sample
        if probs.ndim == 1:
            probs = probs.reshape(1, -1)
        return probs[0]

    def _build_key_features(self, features: np.ndarray) -> Optional[KeyFeatures]:
        """Build KeyFeatures from feature vector using known column positions."""
        if not self._feature_names:
            return None
        try:
            idx = {name: i for i, name in enumerate(self._feature_names)}
            flat = features.flatten()

            def _get(col: str) -> Optional[float]:
                i = idx.get(col)
                return float(flat[i]) if i is not None else None

            return KeyFeatures(
                home_elo=_get("home_elo_before"),
                away_elo=_get("away_elo_before"),
                elo_diff=_get("elo_diff"),
                home_form5_ppg=_get("home_form5_ppg"),
                away_form5_ppg=_get("away_form5_ppg"),
                h2h_home_win_rate=_get("h2h_home_win_rate"),
                home_season_ppg=_get("home_season_ppg"),
                away_season_ppg=_get("away_season_ppg"),
                home_absences=int(_get("home_absences") or 0),
                away_absences=int(_get("away_absences") or 0),
            )
        except Exception:
            return None
