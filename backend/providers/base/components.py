"""Availability semantics for optional provider responses."""

from enum import Enum


class ComponentStatus(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"
