# ai-engine/config/business_constants.py

from enum import Enum
from typing import Dict, FrozenSet
from .core_constants import (
    PlayerPosition, 
    MatchStatus, 
    MatchOutcome,
    API_STATUS_MAPPING,
    API_POSITION_MAPPING,
    API_OUTCOME_MAPPING
)

# ======================== MATCH STATUSES ========================
MatchStatusCategory = MatchStatus
MATCH_STATUS_MAPPING = API_STATUS_MAPPING

# ======================== PLAYER POSITIONS ========================
POSITION_MAPPING = API_POSITION_MAPPING

# ======================== ENTITY TYPES ========================
VALID_ENTITY_TYPES: FrozenSet[str] = frozenset({
    'team', 'player', 'match', 'stadium', 'league', 'referee'
})

# ======================== MATCH OUTCOMES ========================
OUTCOME_MAPPING = API_OUTCOME_MAPPING

# ======================== SEASON CONSTANTS ========================
CURRENT_SEASON_YEAR: int = 2023
SEASON_FORMAT: str = "{start}/{end}"

# ======================== ML LABEL MAPPINGS ========================
class MLOutcomeLabels(Enum):
    """Nhãn số cho bài toán dự đoán kết quả trận đấu"""
    HOME_WIN = 0
    DRAW = 1
    AWAY_WIN = 2
    
    @classmethod
    def from_outcome(cls, outcome: MatchOutcome) -> int:
        mapping = {
            MatchOutcome.HOME: cls.HOME_WIN.value,
            MatchOutcome.DRAW: cls.DRAW.value,
            MatchOutcome.AWAY: cls.AWAY_WIN.value
        }
        return mapping[outcome]
    
    @classmethod
    def to_outcome(cls, label: int) -> MatchOutcome:
        reverse_mapping = {
            cls.HOME_WIN.value: MatchOutcome.HOME,
            cls.DRAW.value: MatchOutcome.DRAW,
            cls.AWAY_WIN.value: MatchOutcome.AWAY
        }
        return reverse_mapping[label]

# ======================== FEATURE CATEGORICAL MAPPINGS ========================
PLAYER_POSITION_LABELS = {
    PlayerPosition.GK: 0,
    PlayerPosition.DEF: 1,
    PlayerPosition.MID: 2,
    PlayerPosition.FWD: 3
}

MATCH_STATUS_LABELS = {
    MatchStatus.SCHEDULED: 0,
    MatchStatus.IN_PROGRESS: 1,
    MatchStatus.FINISHED: 2,
    MatchStatus.POSTPONED: 3,
    MatchStatus.CANCELLED: 4
}

# ======================== COMPLETE LABEL MAPPING API ========================
LABEL_MAPPERS = {
    "match_outcome": {
        "encoder": MLOutcomeLabels.from_outcome,
        "decoder": MLOutcomeLabels.to_outcome
    },
    "player_position": {
        "encoder": lambda pos: PLAYER_POSITION_LABELS.get(pos, -1),
        "decoder": lambda label: next(
            (pos for pos, lbl in PLAYER_POSITION_LABELS.items() if lbl == label), 
            PlayerPosition.MID
        )
    },
    "match_status": {
        "encoder": lambda status: MATCH_STATUS_LABELS.get(status, -1),
        "decoder": lambda label: next(
            (status for status, lbl in MATCH_STATUS_LABELS.items() if lbl == label),
            MatchStatus.SCHEDULED
        )
    }
}