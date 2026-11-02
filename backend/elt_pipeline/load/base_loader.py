# elt_pipeline/load/base_loader.py
"""
Abstract Loader Interface - Dependency Inversion Principle.

The orchestrator depends on AbstractLoader, NOT on any concrete implementation.
Switching storage backend = create new AbstractLoader subclass, change nothing else.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from elt_pipeline.transform.data_structures import ParsedMatchBundle


class LoadResult(Dict[str, Any]):
    """
    Typed result dict returned by bulk_load.
    Keys: total, success, failed, failed_ids.
    """


class AbstractLoader(ABC):
    """
    Contract for any storage backend that accepts ParsedMatchBundle objects.

    Concrete implementations:
      - MatchLoader (PostgreSQL via SQLAlchemy)
      - Future: BigQueryLoader, ParquetLoader, etc.
    """

    @abstractmethod
    def load_bundle(self, bundle: "ParsedMatchBundle") -> int:
        """
        Persist one ParsedMatchBundle.
        Returns the internal match ID (for downstream linking).
        Raises LoaderError on failure.
        """

    @abstractmethod
    def bulk_load(self, bundles: "List[ParsedMatchBundle]") -> LoadResult:
        """
        Persist a list of bundles. Manages individual transactions.
        Returns summary dict: {total, success, failed, failed_ids}.
        Should NOT raise - errors are captured per-bundle.
        """


class LoaderError(Exception):
    """Raised when a loader operation fails unrecoverably."""

