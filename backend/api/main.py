# api/main.py
"""
FastAPI Application Factory.

Design:
  - Lifespan context manager: warm up model + DB connection on startup
  - All routers mounted under /api/v1
  - CORS configured for frontend (localhost:3000 + production domain)
  - Prometheus metrics via prometheus-fastapi-instrumentator
  - Structured request logging middleware
  - Global exception handler returns RFC 7807-style error bodies

Run locally:
    uvicorn api.main:app --reload --port 8000

Production (Docker):
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.dependencies import get_prediction_service
from api.middleware.logging import RequestLoggingMiddleware
from api.routers import health, matches, model, predictions, teams

logger = logging.getLogger(__name__)

# ── Application metadata ──────────────────────────────────────────────────────
APP_TITLE       = "Premier League Match Outcome Prediction API"
APP_DESCRIPTION = """
## EPL Match Outcome Prediction System

Provides calibrated win/draw/loss probabilities for Premier League matches
using a stacking ensemble of XGBoost, LightGBM and CatBoost when a trained
artifact is installed.

### Feature Engineering
- **ELO ratings** (adaptive K-factor, home advantage correction)
- **Rolling form** (last 5 & 10 matches, recency-weighted)
- **Season cumulative stats** (home/away/overall splits)
- **Head-to-head history** (all-time + recent)
- **Squad availability** (injuries & suspensions)
- **Referee tendencies** (home bias, card rate)
- **Rest/fatigue** (days since last match)
- **Derby detection** (local rivalry flag)
- **Attack/defense strength** (Dixon-Coles style parameters)

### Model
- 2-layer stacking: XGBoost + LightGBM + CatBoost → Logistic Regression
- Isotonic probability calibration
- Walk-forward cross-validation (no data leakage)
"""
APP_VERSION = "1.0.0"


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Startup: load model once into memory.
    Shutdown: close DB connections.
    """
    logger.info("API startup - loading prediction model...")
    try:
        svc = get_prediction_service()
        svc.load_model()
        if svc.is_loaded:
            logger.info("Prediction model loaded (version=%s).", svc.model_version)
        else:
            logger.warning("Model not found - predictions unavailable until training completes.")
    except Exception as exc:
        logger.error("Model load failed at startup: %s", exc, exc_info=True)

    yield

    logger.info("API shutdown.")


# ── Application factory ────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """
    Build and configure the FastAPI application.
    Separated from module-level instantiation for testability.
    """
    app = FastAPI(
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    allowed_origins = [
        "http://localhost:3000",        # Next.js dev
        "http://127.0.0.1:3000",
        os.getenv("FRONTEND_URL", ""),  # Production origin via env var
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o for o in allowed_origins if o],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request logging ───────────────────────────────────────────────────────
    app.add_middleware(RequestLoggingMiddleware)

    # ── Prometheus metrics ────────────────────────────────────────────────────
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator(
            should_group_status_codes=True,
            should_respect_env_var=True,
            env_var_name="ENABLE_METRICS",
            excluded_handlers=["/health", "/ready", "/metrics"],
        ).instrument(app).expose(app, endpoint="/metrics")
        logger.info("Prometheus metrics enabled at /metrics.")
    except ImportError:
        logger.warning("prometheus-fastapi-instrumentator not installed - metrics disabled.")

    # ── Global exception handlers ─────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled exception: %s %s → %s",
            request.method, request.url.path, exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": "Internal server error. Please try again."},
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    # Health checks at root (Docker/K8s needs /health without prefix)
    app.include_router(health.router)

    API_PREFIX = "/api/v1"
    app.include_router(matches.router,     prefix=API_PREFIX)
    app.include_router(teams.router,       prefix=API_PREFIX)
    app.include_router(predictions.router, prefix=API_PREFIX)
    app.include_router(model.router,       prefix=API_PREFIX)

    # Root redirect to docs
    @app.get("/", include_in_schema=False)
    async def root():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/docs")

    logger.info("FastAPI application configured. Routes: %d", len(app.routes))
    return app


# ── Module-level app instance ─────────────────────────────────────────────────
# Uvicorn targets: `uvicorn api.main:app`
app = create_app()

