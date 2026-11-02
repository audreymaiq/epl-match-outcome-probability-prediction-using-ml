# api/middleware/logging.py
"""
Request/response structured logging middleware.
Logs method, path, status, duration for every request.
Compatible with structlog for JSON log output in production.
"""

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("api.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs each HTTP request with:
      - method, path, query string
      - response status code
      - duration (ms)
      - client IP

    Skips /health and /metrics to avoid log spam from health checkers.
    """

    SKIP_PATHS = frozenset(["/health", "/ready", "/metrics", "/favicon.ico"])

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        logger.info(
            "%s %s %d %.1fms | client=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request.client.host if request.client else "unknown",
        )
        return response

