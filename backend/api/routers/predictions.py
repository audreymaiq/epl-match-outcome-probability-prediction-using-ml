# api/routers/predictions.py
"""Prediction endpoints - core product feature."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.dependencies import get_db, get_prediction_svc
from api.services.prediction_service import PredictionService
from api.schemas.prediction import PredictRequest, PredictResponse, PredictionRecord
from api.schemas.common import PagedResponse, Pagination

router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.post(
    "",
    response_model=PredictResponse,
    summary="Predict match outcome probabilities",
    description=(
        "Returns calibrated P(Home Win), P(Draw), P(Away Win) for a given fixture. "
        "Provide either `match_id` (for a DB-registered match) or "
        "`home_team_id + away_team_id + match_datetime + season_name + match_week` for a custom fixture."
    ),
)
def predict(
    request: PredictRequest,
    db: Session = Depends(get_db),
    svc: PredictionService = Depends(get_prediction_svc),
) -> PredictResponse:
    return svc.predict(request, db)


@router.get(
    "",
    response_model=PagedResponse[PredictionRecord],
    summary="List stored predictions",
    description="Paginated list of all stored predictions with optional accuracy summary.",
)
def list_predictions(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    svc: PredictionService = Depends(get_prediction_svc),
) -> PagedResponse[PredictionRecord]:
    return svc.list_predictions(db, page=page, page_size=page_size)


@router.get(
    "/model-probabilities/{match_id}",
    response_model=PredictResponse,
    summary="Quick prediction by match ID",
    description="Convenience GET endpoint - equivalent to POST /predictions with match_id.",
)
def predict_by_match_id(
    match_id: int,
    include_breakdown: bool = Query(False, description="Include raw feature vector"),
    db: Session = Depends(get_db),
    svc: PredictionService = Depends(get_prediction_svc),
) -> PredictResponse:
    req = PredictRequest(
        match_id=match_id,
        include_feature_breakdown=include_breakdown,
    )
    return svc.predict(req, db)
