# api/routers/health.py
"""Health check endpoints - used by Docker, K8s, and load balancers."""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.dependencies import get_db, get_prediction_svc
from api.schemas.common import HealthStatus

router = APIRouter(tags=["Health"])

_START_TIME = time.monotonic()
_VERSION = "1.0.0"


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="Basic liveness probe",
    description="Returns 200 if the API is running. Used by Docker HEALTHCHECK.",
)
def health_check(
    db: Session = Depends(get_db),
    prediction_svc=Depends(get_prediction_svc),
) -> HealthStatus:
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return HealthStatus(
        status="ok" if db_status == "connected" else "degraded",
        version=_VERSION,
        database=db_status,
        model_loaded=prediction_svc.is_loaded,
        uptime_seconds=round(time.monotonic() - _START_TIME, 1),
    )


@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
    description="Returns 200 only when the model is loaded and DB is connected. Use for K8s readiness.",
)
def readiness_check(
    db: Session = Depends(get_db),
    prediction_svc=Depends(get_prediction_svc),
):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"ready": False, "reason": "Database unreachable"},
        )

    if not prediction_svc.is_loaded:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"ready": False, "reason": "Model not yet loaded"},
        )

    return {"ready": True, "timestamp": datetime.now(timezone.utc).isoformat()}

