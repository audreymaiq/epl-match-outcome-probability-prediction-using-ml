# api/routers/health.py
"""Health check endpoints - used by Docker, K8s, and load balancers."""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.dependencies import get_db, get_prediction_service, get_competition_dep
from api.schemas.common import HealthStatus

router = APIRouter(tags=["Health"])

_START_TIME = time.monotonic()
_VERSION = "1.0.0"


@router.get("/live", summary="Process liveness without external dependencies")
def liveness():
    return {"alive": True}


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="Database and model diagnostics",
    description="Use /live for liveness and /ready for prediction readiness.",
)
def health_check(
    db: Session = Depends(get_db),
    prediction_svc=Depends(get_prediction_service),
    competition=Depends(get_competition_dep),
) -> HealthStatus:
    model_loaded = False
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    if db_status == "connected":
        try:
            model_loaded = prediction_svc.for_competition(competition).is_loaded
        except Exception:
            model_loaded = False

    return HealthStatus(
        status="ok" if db_status == "connected" else "degraded",
        version=_VERSION,
        database=db_status,
        model_loaded=model_loaded,
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
    prediction_svc=Depends(get_prediction_service),
    competition=Depends(get_competition_dep),
):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"ready": False, "reason": "Database unreachable"},
        )

    try:
        service = prediction_svc.for_competition(competition)
        service.check_readiness(db)
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"ready": False, "reason": "Compatible model and current features are required"},
        )

    return {"ready": True, "timestamp": datetime.now(timezone.utc).isoformat()}

