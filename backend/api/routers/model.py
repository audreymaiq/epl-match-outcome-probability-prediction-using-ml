# api/routers/model.py
"""Model info and performance endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Any, Dict

from api.dependencies import get_db, get_prediction_svc
from api.services.model_service import ModelService
from api.services.prediction_service import PredictionService

router = APIRouter(prefix="/model", tags=["Model"])


@router.get(
    "/info",
    summary="Get current model metadata",
    description="Returns version, training seasons, feature count, CV metrics.",
)
def model_info(
    svc: PredictionService = Depends(get_prediction_svc),
) -> Dict[str, Any]:
    model_svc = ModelService()
    return model_svc.get_model_info(svc)


@router.get(
    "/performance",
    summary="Model prediction accuracy on past matches",
    description=(
        "Computes accuracy of past predictions vs actual outcomes. "
        "Requires predictions to have been stored (via POST /predictions)."
    ),
)
def model_performance(
    db: Session = Depends(get_db),
    svc: PredictionService = Depends(get_prediction_svc),
) -> Dict[str, Any]:
    model_svc = ModelService()
    return model_svc.get_performance(db, svc.model_version if svc.is_loaded else None)


@router.get(
    "/features",
    summary="List all feature names used by the model",
)
def model_features(
    svc: PredictionService = Depends(get_prediction_svc),
) -> Dict[str, Any]:
    if not svc.is_loaded:
        return {"loaded": False, "features": []}
    return {
        "loaded": True,
        "n_features": len(svc._feature_names),
        "features": svc._feature_names,
    }

