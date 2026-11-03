"""
Abstract base for all feature computers.

Each computer is responsible for ONE aggregation type.
The FeaturePipelineOrchestrator calls them in dependency order.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AbstractFeatureComputer(ABC):
    """
    Contract for a feature computer.

    A computer reads raw match data from DB and writes aggregated features
    back to a designated feature table (e.g. TeamFormStats, HeadToHeadStats).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for logging."""

    @abstractmethod
    def compute(
        self,
        session: Session,
        season_name: Optional[str] = None,
    ) -> int:
        """
        Compute and upsert features.

        Args:
            session:     Active SQLAlchemy session.
            season_name: Limit computation to this season (e.g. '2023/24').
                         None = recompute all seasons.

        Returns:
            Number of rows upserted.

        Raises:
            ComputerError on unrecoverable failure.
        """


class ComputerError(Exception):
    """Raised when a feature computer fails unrecoverably."""

