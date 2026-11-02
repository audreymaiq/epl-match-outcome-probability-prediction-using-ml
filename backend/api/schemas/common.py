# api/schemas/common.py
"""Shared response schemas - pagination, errors, envelopes."""

from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class Pagination(BaseModel):
    page: int = Field(ge=1, description="Current page (1-indexed)")
    page_size: int = Field(ge=1, le=100, description="Items per page")
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class PagedResponse(BaseModel, Generic[T]):
    data: List[T]
    pagination: Pagination


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    errors: List[ErrorDetail]


class HealthStatus(BaseModel):
    status: str                     # "ok" | "degraded" | "down"
    version: str
    database: str                   # "connected" | "disconnected"
    model_loaded: bool
    uptime_seconds: float

