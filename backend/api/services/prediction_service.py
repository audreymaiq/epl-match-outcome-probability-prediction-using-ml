# api/services/prediction_service.py
"""
Prediction Service - core ML inference path.

Responsibilities:
  1. Load trained ensemble model from disk (once at startup)
  2. Build feature vector for a match using FeatureExtractor
  3. Run inference → calibrated probabilities [P(H), P(D), P(A)]
  4. Return selected input features for context
  5. Persist prediction to DB (for monitoring/evaluation)

Design:
  - Model loading is lazy but thread-safe (called once via @lru_cache dependency)
  - Stateless predict() method: safe for concurrent requests
  - Returns predictions only when a validated artifact is loaded
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import text
from ml.inference.predictor import ModelPredictor
from ml.config import parse_ml_config

from api.schemas.prediction import (
    PredictRequest, PredictResponse, ProbabilityBreakdown, KeyFeatures,
    PredictionRecord,
)
from api.schemas.common import PagedResponse, Pagination
from api.exceptions import ModelNotLoadedException, PredictionFailedException

logger = logging.getLogger(__name__)

class PredictionService:
    """
    Encapsulates all ML inference logic.

    Thread-safe: model and metadata are read-only after load_model().
    """

    def __init__(self, model_path: Optional[Path] = None):
        self._predictor = ModelPredictor(model_path)

    def load_model(self) -> None:
        """
        Load model from disk. Called once at application startup.
        Raises RuntimeError if model file is missing.
        """
        try:
            if not self._predictor.load():
                logger.warning("Model file not found at %s. Predictions are unavailable.", self._predictor.path)
            else:
                logger.info("Model loaded from %s | version=%s | features=%d",
                            self._predictor.path, self.model_version, len(self._predictor.feature_names))
        except Exception as exc:
            logger.error("Failed to load model from %s: %s", self._predictor.path, exc, exc_info=True)
            raise RuntimeError(f"Model loading failed: {exc}") from exc

    @property
    def is_loaded(self) -> bool:
        return self._predictor.is_loaded

    @property
    def model_version(self) -> str:
        return self._predictor.version

    @property
    def model_metadata(self) -> Dict[str, Any]:
        return dict(self._predictor.metadata)

    @property
    def feature_names(self) -> list[str]:
        return list(self._predictor.feature_names)

    def predict(
        self,
        request: PredictRequest,
        db_session,
        *,
        record_prediction: bool = True,
    ) -> PredictResponse:
        """
        Main inference method.

        Args:
            request:    Validated PredictRequest.
            db_session: SQLAlchemy session for feature extraction.
            record_prediction: Persist the first prediction for a registered fixture.

        Returns:
            PredictResponse with calibrated probabilities.

        Raises:
            ModelNotLoadedException if model not ready.
            PredictionFailedException if feature extraction or inference fails.
        """
        if not self.is_loaded:
            raise ModelNotLoadedException()

        try:
            feature_frame, match_meta = self._extract_features(request, db_session)
        except Exception as exc:
            logger.error("Feature extraction failed: %s", exc, exc_info=True)
            raise PredictionFailedException(reason=str(exc)) from exc

        try:
            features, probs = self._predictor.predict(feature_frame)
        except Exception as exc:
            logger.error("Model inference failed: %s", exc, exc_info=True)
            raise PredictionFailedException(reason=f"Inference error: {exc}") from exc

        # Build key features from raw vector
        key_features = self._build_key_features(features)

        feature_vector = None
        if request.include_feature_breakdown and self._predictor.feature_names:
            feature_vector = dict(zip(self._predictor.feature_names, features.flatten().tolist()))

        predicted_outcome = ["H", "D", "A"][int(np.argmax(probs))]
        confidence = float(np.max(probs))

        response = PredictResponse(
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
        if record_prediction and response.match_id is not None:
            self._save_prediction(db_session, response)
        return response

    def _save_prediction(self, db_session, response: PredictResponse) -> None:
        """Keep the first prediction for each fixture and model version."""
        db_session.execute(text("""
            INSERT INTO "Predictions" (
                match_id, model_version, predicted_outcome,
                home_win_prob, draw_prob, away_win_prob, confidence
            ) VALUES (
                :match_id, :model_version, :predicted_outcome,
                :home_win_prob, :draw_prob, :away_win_prob, :confidence
            )
            ON CONFLICT (match_id, model_version) DO NOTHING
        """), {
            "match_id": response.match_id,
            "model_version": response.model_version,
            "predicted_outcome": response.predicted_outcome,
            "home_win_prob": response.probabilities.home_win,
            "draw_prob": response.probabilities.draw,
            "away_win_prob": response.probabilities.away_win,
            "confidence": response.confidence,
        })

    def list_predictions(
        self,
        db_session,
        page: int = 1,
        page_size: int = 25,
    ) -> PagedResponse[PredictionRecord]:
        """
        List stored predictions from DB with pagination.

        The schema is required to exist before the API starts serving requests.
        """
        offset = (page - 1) * page_size
        total = int(db_session.execute(text('SELECT COUNT(*) FROM "Predictions"')).scalar() or 0)

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
                COALESCE(m.outcome::text, p.actual_outcome) AS actual_outcome,
                CASE WHEN m.outcome IS NOT NULL
                    THEN p.predicted_outcome = m.outcome::text
                    ELSE p.was_correct END AS was_correct,
                to_char(p.created_at, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS created_at
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
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Use FeatureExtractor to build feature vector from DB.
        Returns (feature_array shape [1, n_features], match_metadata dict).
        """
        from ml.features.feature_extractor import FeatureExtractor

        training_config = self._predictor.metadata.get("training_config")
        if training_config is None:
            raise ValueError("Model artifact has no feature configuration")
        extractor = FeatureExtractor(db_session, config=parse_ml_config(training_config))

        if request.match_id is not None:
            meta = extractor.get_match_meta(request.match_id)
            if not meta:
                raise ValueError(f"Match {request.match_id} does not exist.")
            if meta.get("status") != "SCHEDULED" or meta["match_datetime"] <= datetime.now(timezone.utc):
                raise ValueError("Predictions are only available before scheduled matches begin.")
            df = extractor.extract_for_match(request.match_id)
            if df is None or df.empty:
                raise ValueError(f"No features found for match_id={request.match_id}")
        else:
            df, meta = extractor.extract_for_fixture(
                home_team_id=request.home_team_id,
                away_team_id=request.away_team_id,
                match_datetime=request.match_datetime,
                season_name=request.season_name,
                match_week=request.match_week,
            )

        return df, meta

    def _build_key_features(self, features: np.ndarray) -> Optional[KeyFeatures]:
        """Build KeyFeatures from feature vector using known column positions."""
        if not self._predictor.feature_names:
            return None
        try:
            idx = {name: i for i, name in enumerate(self._predictor.feature_names)}
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
