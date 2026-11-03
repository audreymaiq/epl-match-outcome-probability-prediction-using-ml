"""
ELO Computer - pipeline adapter for ml/elo/elo_builder.py.

Delegates actual ELO computation to the ml layer.
This keeps ml.features.batch/ as a thin orchestration layer.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from ml.features.batch.computers.base_computer import AbstractFeatureComputer
from ml.elo.elo_builder import EloBuilder

logger = logging.getLogger(__name__)


class EloComputer(AbstractFeatureComputer):

    @property
    def name(self) -> str:
        return "EloRatings"

    def compute(self, session: Session, season_name: Optional[str] = None) -> int:
        logger.info("Computing EloRatings (via EloBuilder)...")
        builder = EloBuilder(session)
        builder.build_from_db()
        rows = builder.save_to_db()
        logger.info("EloRatings: saved %d rows.", rows)
        return rows

