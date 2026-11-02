# api/middleware/__init__.py
from api.middleware.logging import RequestLoggingMiddleware

__all__ = ["RequestLoggingMiddleware"]

