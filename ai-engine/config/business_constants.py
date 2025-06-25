# ai-engine/config/business_constants.py

from enum import Enum
from typing import List, Tuple, FrozenSet, Dict, Any, Optional
from functools import lru_cache
from config.settings import get_config
from .core_constants import (
    PlayerPosition,
    MatchStatus,
    MatchOutcome,
    API_STATUS_MAPPING,
    API_POSITION_MAPPING,
    API_OUTCOME_MAPPING
)

# ======================== CONFIGURATION LOADING ========================
@lru_cache(maxsize=1)
def _get_config():
    """Cached lazy load configuration to avoid circular imports"""
    return get_config()

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
@lru_cache(maxsize=1)
def get_current_season() -> Tuple[int, int]:
    """Get current season dynamically with caching"""
    return _get_config().seasons.current_season

@lru_cache(maxsize=1)
def get_last_completed_season() -> Tuple[int, int]:
    """Get last completed season dynamically with caching"""
    return _get_config().seasons.last_completed_season

@lru_cache(maxsize=16)  
def get_seasons_to_fetch(start_year: int = 2018, min_count: int = 5) -> List[Tuple[int, int]]:
    """Get seasons to fetch with parameters and caching"""
    return _get_config().seasons.get_seasons_to_fetch(start_year, min_count)

# Constants that can be computed once
SEASON_FORMAT: str = "{start}/{end}"

# ======================== SEASONS TO FETCH ========================
# Backward compatibility - use default parameters
def get_default_seasons_to_fetch() -> List[Tuple[int, int]]:
    """Get default seasons to fetch"""
    return get_seasons_to_fetch()

# For backward compatibility
SEASONS_TO_FETCH = get_default_seasons_to_fetch()

# ======================== ML LABEL MAPPINGS ========================
class MLOutcomeLabels(Enum):
    """Nhãn số cho bài toán dự đoán kết quả trận đấu"""
    HOME_WIN = 0
    DRAW = 1
    AWAY_WIN = 2
    UNKNOWN = -1

    @classmethod
    def from_outcome(cls, outcome: str) -> int:
        """Convert MatchOutcome to ML label"""
        mapping = {
            MatchOutcome.HOME: cls.HOME_WIN.value,
            MatchOutcome.DRAW: cls.DRAW.value,
            MatchOutcome.AWAY: cls.AWAY_WIN.value,
            MatchOutcome.UNKNOWN: cls.UNKNOWN.value
        }
        return mapping.get(outcome, cls.UNKNOWN.value)
    
    @classmethod
    def to_outcome(cls, label: int) -> str:
        """Convert ML label back to MatchOutcome"""
        reverse_mapping = {
            cls.HOME_WIN.value: MatchOutcome.HOME,
            cls.DRAW.value: MatchOutcome.DRAW,
            cls.AWAY_WIN.value: MatchOutcome.AWAY,
            cls.UNKNOWN.value: MatchOutcome.UNKNOWN
        }
        return reverse_mapping.get(label, MatchOutcome.UNKNOWN)

    @classmethod
    def get_all_labels(cls) -> List[int]:
        """Get all valid ML labels (excluding UNKNOWN)"""
        return [cls.HOME_WIN.value, cls.DRAW.value, cls.AWAY_WIN.value]
    
    @classmethod
    def get_label_names(cls) -> Dict[int, str]:
        """Get mapping from label to readable name"""
        return {
            cls.HOME_WIN.value: "Home Win",
            cls.DRAW.value: "Draw", 
            cls.AWAY_WIN.value: "Away Win",
            cls.UNKNOWN.value: "Unknown"
        }

# ======================== FEATURE CATEGORICAL MAPPINGS ========================
PLAYER_POSITION_LABELS: Dict[str, int] = {
    PlayerPosition.GK: 0,
    PlayerPosition.DEF: 1,
    PlayerPosition.MID: 2,
    PlayerPosition.FWD: 3,
    PlayerPosition.UNKNOWN: -1
}

MATCH_STATUS_LABELS: Dict[str, int] = {
    MatchStatus.SCHEDULED: 0,
    MatchStatus.IN_PROGRESS: 1,
    MatchStatus.FINISHED: 2,
    MatchStatus.POSTPONED: 3,
    MatchStatus.CANCELLED: 4,
    MatchStatus.ABANDONED: 5,
    MatchStatus.UNKNOWN: -1
}

# Reverse mappings for decoding
POSITION_LABELS_REVERSE: Dict[int, str] = {
    v: k for k, v in PLAYER_POSITION_LABELS.items()
}

STATUS_LABELS_REVERSE: Dict[int, str] = {
    v: k for k, v in MATCH_STATUS_LABELS.items()
}

# ======================== COMPLETE LABEL MAPPING API ========================
def encode_player_position(pos: str) -> int:
    """Encode player position to numeric label"""
    return PLAYER_POSITION_LABELS.get(pos, PLAYER_POSITION_LABELS[PlayerPosition.UNKNOWN])

def decode_player_position(label: int) -> str:
    """Decode numeric label to player position"""
    return POSITION_LABELS_REVERSE.get(label, PlayerPosition.UNKNOWN)

def encode_match_status(status: str) -> int:
    """Encode match status to numeric label"""
    return MATCH_STATUS_LABELS.get(status, MATCH_STATUS_LABELS[MatchStatus.UNKNOWN])

def decode_match_status(label: int) -> str:
    """Decode numeric label to match status"""
    return STATUS_LABELS_REVERSE.get(label, MatchStatus.UNKNOWN)

# Complete label mapping API with enhanced error handling
LABEL_MAPPERS: Dict[str, Dict[str, Any]] = {
    "match_outcome": {
        "encoder": MLOutcomeLabels.from_outcome,
        "decoder": MLOutcomeLabels.to_outcome,
        "valid_labels": MLOutcomeLabels.get_all_labels(),
        "label_names": MLOutcomeLabels.get_label_names()
    },
    "player_position": {
        "encoder": encode_player_position,
        "decoder": decode_player_position,
        "valid_labels": [lbl for lbl in PLAYER_POSITION_LABELS.values() if lbl != -1],
        "label_names": {lbl: pos for pos, lbl in PLAYER_POSITION_LABELS.items()}
    },
    "match_status": {
        "encoder": encode_match_status,
        "decoder": decode_match_status, 
        "valid_labels": [lbl for lbl in MATCH_STATUS_LABELS.values() if lbl != -1],
        "label_names": {lbl: status for status, lbl in MATCH_STATUS_LABELS.items()}
    }
}

# ======================== MATCH CONSTANTS ========================
# Match timing constants
MINUTES_IN_MATCH = 90
EXTRA_TIME_MINUTES = 30
PENALTY_SHOOTOUT_ROUNDS = 5
HALFTIME_BREAK_MINUTES = 15

# Additional match periods
FIRST_HALF_MINUTES = 45
SECOND_HALF_MINUTES = 45
FIRST_EXTRA_TIME_MINUTES = 15
SECOND_EXTRA_TIME_MINUTES = 15

# ======================== STATISTICAL THRESHOLDS ========================
# Performance thresholds for analysis
POSSESSION_THRESHOLD = 0.6  # 60% ball possession
SHOTS_ON_TARGET_THRESHOLD = 5
CORNERS_THRESHOLD = 7
CARDS_THRESHOLD = 3
FOULS_THRESHOLD = 15
PASS_ACCURACY_THRESHOLD = 0.8  # 80% pass accuracy

# Goal scoring thresholds
HIGH_SCORING_THRESHOLD = 4  # 4+ goals total
LOW_SCORING_THRESHOLD = 1   # 1 or fewer goals

# ======================== TEAM PERFORMANCE CATEGORIES ========================
class TeamPerformanceCategory(Enum):
    """Categories for team performance analysis"""
    EXCELLENT = "excellent"
    GOOD = "good" 
    AVERAGE = "average"
    POOR = "poor"
    VERY_POOR = "very_poor"

# Performance thresholds (points per game)
PERFORMANCE_THRESHOLDS = {
    TeamPerformanceCategory.EXCELLENT: 2.5,  # 95+ points in 38 games
    TeamPerformanceCategory.GOOD: 2.0,       # 76+ points
    TeamPerformanceCategory.AVERAGE: 1.5,    # 57+ points  
    TeamPerformanceCategory.POOR: 1.0,       # 38+ points
    TeamPerformanceCategory.VERY_POOR: 0.0   # Below 38 points
}

def categorize_team_performance(points_per_game: float) -> TeamPerformanceCategory:
    """Categorize team performance based on points per game"""
    for category, threshold in PERFORMANCE_THRESHOLDS.items():
        if points_per_game >= threshold:
            return category
    return TeamPerformanceCategory.VERY_POOR

# ======================== LEAGUE CONSTANTS ========================
PREMIER_LEAGUE_TEAMS = 20
PREMIER_LEAGUE_MATCHES_PER_SEASON = 380  # 20 teams * 19 games * 2
PREMIER_LEAGUE_ROUNDS = 38

# Points system
WIN_POINTS = 3
DRAW_POINTS = 1
LOSS_POINTS = 0

# ======================== UTILITY FUNCTIONS ========================
def format_season(start_year: int, end_year: int) -> str:
    """Format season string consistently"""
    return SEASON_FORMAT.format(start=start_year, end=str(end_year)[-2:])

def parse_season_string(season_str: str) -> Tuple[int, int]:
    """Parse season string back to start/end years"""
    try:
        if "/" in season_str:
            start_str, end_str = season_str.split("/")
            start_year = int(start_str)
            # Handle 2-digit or 4-digit end year
            if len(end_str) == 2:
                end_year = int(f"20{end_str}")
            else:
                end_year = int(end_str)
            return (start_year, end_year)
    except (ValueError, IndexError):
        pass
    raise ValueError(f"Invalid season format: {season_str}")

def is_valid_season(start_year: int, end_year: int) -> bool:
    """Validate season years"""
    return (
        2000 <= start_year <= 2050 and
        2000 <= end_year <= 2050 and
        end_year == start_year + 1
    )

# ======================== EXPORT VALIDATION ========================
def validate_constants():
    """Validate all constants are properly defined"""
    errors = []
    
    # Get all constants from classes for validation
    position_constants = [getattr(PlayerPosition, attr) for attr in dir(PlayerPosition) 
                        if not attr.startswith('_') and isinstance(getattr(PlayerPosition, attr), str)]
    status_constants = [getattr(MatchStatus, attr) for attr in dir(MatchStatus) 
                        if not attr.startswith('_') and isinstance(getattr(MatchStatus, attr), str)]
    
    # Check enum mappings are complete
    if len(PLAYER_POSITION_LABELS) != len(position_constants):
        errors.append(f"PLAYER_POSITION_LABELS incomplete: expected {len(position_constants)}, got {len(PLAYER_POSITION_LABELS)}")
    
    if len(MATCH_STATUS_LABELS) != len(status_constants):
        errors.append(f"MATCH_STATUS_LABELS incomplete: expected {len(status_constants)}, got {len(MATCH_STATUS_LABELS)}")
        
    # Check reverse mappings
    if len(POSITION_LABELS_REVERSE) != len(PLAYER_POSITION_LABELS):
        errors.append("POSITION_LABELS_REVERSE incomplete")
        
    if len(STATUS_LABELS_REVERSE) != len(MATCH_STATUS_LABELS):
        errors.append("STATUS_LABELS_REVERSE incomplete")
    
    # Check label mappers
    required_keys = {"encoder", "decoder", "valid_labels", "label_names"}
    for mapper_name, mapper in LABEL_MAPPERS.items():
        missing_keys = required_keys - set(mapper.keys())
        if missing_keys:
            errors.append(f"LABEL_MAPPERS['{mapper_name}'] missing keys: {missing_keys}")
    
    if errors:
        raise ValueError(f"Business constants validation failed: {'; '.join(errors)}")

# Run validation on import (with error handling)
try:
    validate_constants()
except Exception as e:
    # Log warning but don't crash on import
    import logging
    try:
        logging.warning(f"Business constants validation warning: {e}")
    except:
        print(f"WARNING: Business constants validation: {e}")