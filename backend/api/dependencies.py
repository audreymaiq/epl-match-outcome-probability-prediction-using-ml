# api/dependencies.py
"""
FastAPI dependency injection.

Provides:
  - get_db()             → SQLAlchemy Session (request-scoped)
  - get_prediction_svc() → PredictionService singleton
  - get_model_svc()      → ModelService singleton
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Generator, TYPE_CHECKING

from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status, Query
from config.competitions import get_competition

from utils.db_connector import DatabaseConnector

if TYPE_CHECKING:
    from api.services.prediction_service import PredictionService
    from api.services.model_service import ModelService

logger = logging.getLogger(__name__)


# ── Database session ──────────────────────────────────────────────────────────

def get_competition_dep(league: str | None = Query(None)):
    try:
        return get_competition(league)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

def get_db() -> Generator[Session, None, None]:
    """
    Yields a SQLAlchemy session per request.
    Commits on success, rolls back on exception, always closes.
    """
    session = DatabaseConnector.get_session()
    try:
        yield session
        session.commit()
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        logger.error("Unhandled exception in request; rolling back session: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please try again later.",
        ) from exc
    finally:
        session.close()


# ── Service singletons ────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_prediction_service() -> "PredictionService":
    """
    Singleton PredictionService - model loaded once at startup.
    @lru_cache ensures only one instance across all requests.
    """
    from api.services.prediction_service import PredictionService
    svc = PredictionService()
    svc.load_model()
    return svc


@lru_cache(maxsize=1)
def get_model_service() -> "ModelService":
    from api.services.model_service import ModelService
    return ModelService()


# ── FastAPI dependency callables ──────────────────────────────────────────────

def get_prediction_svc(
    svc: "PredictionService" = Depends(get_prediction_service),
    competition=Depends(get_competition_dep),
) -> "PredictionService":
    return svc.for_competition(competition)


def get_model_svc(
    svc: "ModelService" = Depends(get_model_service),
) -> "ModelService":
    return svc

