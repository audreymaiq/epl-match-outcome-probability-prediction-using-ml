# ai-engine/config/core_constants.py

from typing import Optional, Dict, Union
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MatchStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"
    ABANDONED = "ABANDONED"
    UNKNOWN = "Unknown"
class PlayerPosition(str, Enum):
    GK = "GK"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"
    UNKNOWN = "Unknown"

class MatchOutcome(str, Enum):
    HOME = "H"
    DRAW = "D"
    AWAY = "A"
    UNKNOWN = "Unknown"

class PlayerStatus(str, Enum):
    AVAILABLE = "Available"
    AWAY_ON_INTL_DUTY = "Away on Intl Duty"
    MISSING_FIXTURE = "Missing Fixture"
    QUESTIONABLE = "Questionable"
    INJURED = "Injured"
    SUSPENDED = "Suspended"
    UNKNOWN = "Unknown"

class MatchEventType(str, Enum):
    GOAL = 'goal'
    OWN_GOAL = 'own goal'
    PENALTY_GOAL = 'penalty goal'
    MISSED_PENALTY = 'missed penalty'
    YELLOW_CARD = 'yellow card'
    RED_CARD = 'red card'
    SUBSTITUTION = 'substitution'
    VAR_DECISION = 'var decision'
    GOAL_CANCELLED = 'goal cancelled'
    PENALTY_CONFIRMED = 'penalty confirmed'
    INJURY = 'injury'
    CORNER_KICK = 'corner kick'
    FREE_KICK = 'free kick'
    OFFSIDE = 'offside'
    FOUL = 'foul'
    CORNER = 'corner'
    PENALTY = 'penalty'
    UNKNOWN = 'Unknown'

class MatchPeriod(str, Enum):
    FIRST_HALF = '1H'
    SECOND_HALF = '2H'
    EXTRA_TIME_1 = 'ET1'
    EXTRA_TIME_2 = 'ET2'
    PENALTIES = 'PEN'
    UNKNOWN = 'Unknown'

# --- Dictionaries Mapping từ API về hằng số chuẩn hóa ---

# SofaScore status mapping 
SOFASCORE_STATUS_MAPPING = {
    # Scheduled statuses
    "notstarted": MatchStatus.SCHEDULED,
    "scheduled": MatchStatus.SCHEDULED,
    
    # In-Play statuses  
    "inprogress": MatchStatus.IN_PROGRESS,
    "1st_half": MatchStatus.IN_PROGRESS,
    "2nd_half": MatchStatus.IN_PROGRESS,
    "halftime": MatchStatus.IN_PROGRESS,
    "extra_time": MatchStatus.IN_PROGRESS,
    "penalties": MatchStatus.IN_PROGRESS,
    "break_time": MatchStatus.IN_PROGRESS,
    "suspended": MatchStatus.IN_PROGRESS,
    "interrupted": MatchStatus.IN_PROGRESS,
    
    # Finished statuses
    "finished": MatchStatus.FINISHED,
    "ended": MatchStatus.FINISHED,
    "after_extra_time": MatchStatus.FINISHED,
    "after_penalties": MatchStatus.FINISHED,
    "awarded": MatchStatus.FINISHED,
    "walkover": MatchStatus.FINISHED,
    
    # Postponed
    "postponed": MatchStatus.POSTPONED,
    
    # Cancelled
    "cancelled": MatchStatus.CANCELLED,
    "canceled": MatchStatus.CANCELLED,
    
    # Abandoned
    "abandoned": MatchStatus.ABANDONED
}

# SofaScore position mapping - keys normalized to lowercase
SOFASCORE_POSITION_MAPPING = {
    "g": PlayerPosition.GK,
    "d": PlayerPosition.DEF,
    "m": PlayerPosition.MID,
    "f": PlayerPosition.FWD,
    "goalkeeper": PlayerPosition.GK,
    "defender": PlayerPosition.DEF,
    "midfielder": PlayerPosition.MID,
    "forward": PlayerPosition.FWD,
    "attacker": PlayerPosition.FWD
}

# SofaScore outcome mapping - keys normalized to string
SOFASCORE_OUTCOME_MAPPING = {
    "1": MatchOutcome.HOME,
    "2": MatchOutcome.AWAY,
    "0": MatchOutcome.DRAW,
    "3": MatchOutcome.DRAW,
    "home": MatchOutcome.HOME,
    "away": MatchOutcome.AWAY,
    "draw": MatchOutcome.DRAW
}

# SofaScore player availability mapping
SOFASCORE_PLAYER_AVAILABILITY_MAPPING = {
    "missing": PlayerStatus.MISSING_FIXTURE,
    "questionable": PlayerStatus.QUESTIONABLE,
    "injured": PlayerStatus.INJURED,
    "suspended": PlayerStatus.SUSPENDED,
    "doubt": PlayerStatus.QUESTIONABLE,
    "doubtful": PlayerStatus.QUESTIONABLE
}

SOFASCORE_EVENT_MAPPING = {
    "goal": MatchEventType.GOAL,
    "ownGoal": MatchEventType.OWN_GOAL,
    "penalty": MatchEventType.PENALTY_GOAL,
    "penaltyMissed": MatchEventType.MISSED_PENALTY,
    "yellowCard": MatchEventType.YELLOW_CARD,
    "redCard": MatchEventType.RED_CARD,
    "yellowRed": MatchEventType.RED_CARD, 
    "secondYellow": MatchEventType.RED_CARD, # secondYellow cũng là thẻ đỏ
    "substitution": MatchEventType.SUBSTITUTION,
    "varDecision": MatchEventType.VAR_DECISION,
    "goalCancelled": MatchEventType.GOAL_CANCELLED,
    "penaltyAwarded": MatchEventType.PENALTY_CONFIRMED,
    "injury": MatchEventType.INJURY,
    "cornerKick": MatchEventType.CORNER_KICK,
    "freeKick": MatchEventType.FREE_KICK,
    "offside": MatchEventType.OFFSIDE,
    "foul": MatchEventType.FOUL,
    "corner": MatchEventType.CORNER,
}

SOFASCORE_PERIOD_MAPPING = {
    "1": MatchPeriod.FIRST_HALF,
    "2": MatchPeriod.SECOND_HALF,
    "3": MatchPeriod.EXTRA_TIME_1,
    "4": MatchPeriod.EXTRA_TIME_2,
    "5": MatchPeriod.PENALTIES
}

# Legacy API-Football mapping (kept for reference/migration)
API_FOOTBALL_STATUS_MAPPING = {
    # Scheduled statuses
    "TBD": MatchStatus.SCHEDULED,   # Time To Be Defined
    "NS": MatchStatus.SCHEDULED,    # Not Started

    # In-Play statuses
    "1H": MatchStatus.IN_PROGRESS,  # First Half
    "2H": MatchStatus.IN_PROGRESS,  # Second Half
    "HT": MatchStatus.IN_PROGRESS,  # Halftime
    "ET": MatchStatus.IN_PROGRESS,  # Extra Time
    "P": MatchStatus.IN_PROGRESS,   # Penalty In Progress
    "BT": MatchStatus.IN_PROGRESS,  # Break Time during extra time
    "LIVE": MatchStatus.IN_PROGRESS,# Live (rare cases)
    "SUSP": MatchStatus.IN_PROGRESS,# Match Suspended (In Play)
    "INT": MatchStatus.IN_PROGRESS, # Match Interrupted (In Play)

    # Finished statuses
    "FT": MatchStatus.FINISHED,     # Match Finished
    "AET": MatchStatus.FINISHED,    # After Extra Time
    "PEN": MatchStatus.FINISHED,    # After Penalty Shootout
    "AWD": MatchStatus.FINISHED,    # Technical Loss / Awarded
    "WO": MatchStatus.FINISHED,     # Walkover

    # Postponed
    "PST": MatchStatus.POSTPONED,   # Postponed

    # Cancelled
    "CANC": MatchStatus.CANCELLED,  # Cancelled

    # Abandoned
    "ABD": MatchStatus.ABANDONED    # Abandoned
}

# Legacy API-Football outcome mapping - keys normalized to lowercase
API_FOOTBALL_OUTCOME_MAPPING = {
    "home": MatchOutcome.HOME,
    "draw": MatchOutcome.DRAW,
    "away": MatchOutcome.AWAY
}

# Legacy API-Football position mapping - keys normalized to lowercase
API_FOOTBALL_POSITION_MAPPING = {
    "goalkeeper": PlayerPosition.GK,
    "defender": PlayerPosition.DEF,
    "midfielder": PlayerPosition.MID,
    "attacker": PlayerPosition.FWD
}

# Legacy API-Football player availability mapping
API_FOOTBALL_PLAYER_AVAILABILITY_MAPPING = {
    "missing fixture": PlayerStatus.MISSING_FIXTURE,
    "questionable": PlayerStatus.QUESTIONABLE
}

# --- Các hàm Mapping thống nhất - Trả về giá trị chuẩn hóa hoặc None ---

# Unified mapping functions for easy switching between APIs
def get_match_status(api_status: Optional[str], api_type: str = "sofascore") -> Optional[MatchStatus]:
    """
    Nhận trạng thái từ API và trả về trạng thái chuẩn hóa hoặc None nếu không xác định.
    """
    if not isinstance(api_status, str) or not api_status.strip():
        return None

    if api_type == "sofascore":
        return SOFASCORE_STATUS_MAPPING.get(api_status.lower())
    elif api_type == "api_football":
        return API_FOOTBALL_STATUS_MAPPING.get(api_status.upper())
    
    return None

def get_player_position(api_position: Optional[str], api_type: str = "sofascore") -> Optional[PlayerPosition]:
    """
    Nhận vị trí từ API và trả về vị trí chuẩn hóa hoặc None nếu không xác định.
    """
    if not isinstance(api_position, str) or not api_position.strip():
        return None

    normalized_pos = api_position.lower()
    if api_type == "sofascore":
        return SOFASCORE_POSITION_MAPPING.get(normalized_pos)
    elif api_type == "api_football":
        return API_FOOTBALL_POSITION_MAPPING.get(normalized_pos)
    
    return None

def get_match_outcome(api_outcome: Optional[Union[int, str]], api_type: str = "sofascore") -> Optional[MatchOutcome]:
    """
    Nhận kết quả từ API và trả về kết quả chuẩn hóa hoặc None nếu không xác định.
    """
    if api_outcome is None:
        return None
        
    normalized_outcome = str(api_outcome).lower()
    
    if api_type == "sofascore":
        return SOFASCORE_OUTCOME_MAPPING.get(normalized_outcome)
    elif api_type == "api_football":
        return API_FOOTBALL_OUTCOME_MAPPING.get(normalized_outcome)

    return None
        
def get_player_availability(api_status: Optional[str], api_type: str = "sofascore") -> Optional[PlayerStatus]:
    """
    Nhận trạng thái sẵn sàng của cầu thủ từ API và trả về trạng thái chuẩn hóa hoặc None.
    """
    if not isinstance(api_status, str) or not api_status.strip():
        return None
        
    normalized_status = api_status.lower()
    
    if api_type == "sofascore":
        return SOFASCORE_PLAYER_AVAILABILITY_MAPPING.get(normalized_status)
    elif api_type == "api_football":
        return API_FOOTBALL_PLAYER_AVAILABILITY_MAPPING.get(normalized_status)
    
    return None

# Hàm dịch cho Event Type
def get_event_type(api_event_type: Optional[str], api_type: str = "sofascore") -> Optional[MatchEventType]:
    """Nhận loại sự kiện từ API và trả về Enum chuẩn hóa."""
    if not isinstance(api_event_type, str) or not api_event_type.strip(): return None
    if api_type == "sofascore":
        result = SOFASCORE_EVENT_MAPPING.get(api_event_type)
        if not result:
            logger.debug(f"Unknown SofaScore event type: '{api_event_type}'")
        return result
    return None

#  Hàm dịch cho Match Period
def get_match_period(api_period: Optional[Union[int, str]], api_type: str = "sofascore") -> Optional[MatchPeriod]:
    """Nhận hiệp đấu từ API và trả về Enum chuẩn hóa."""
    if api_period is None: return None
    normalized_period = str(api_period)
    if api_type == "sofascore":
        result = SOFASCORE_PERIOD_MAPPING.get(normalized_period)
        if not result:
            logger.debug(f"Unknown SofaScore period: '{api_period}'")
        return result
    return None

# --- Các hằng số khác không liên quan trực tiếp đến schema ENUMs ---
class SofascoreWinnerCodes:
    """SofaScore winner code constants"""
    HOME_WIN = 1
    AWAY_WIN = 2
    DRAW = 0

# SofaScore specific constants
class SofascoreConstants:
    # Premier League tournament ID
    EPL_TOURNAMENT_ID = 17
    
    # Common season IDs (update these as needed)
    SEASON_IDS = {
        "2017/18": 13380,
        "2018/19": 17359,
        "2019/20": 23776,
        "2020/21": 29415,
        "2021/22": 37036,
        "2022/23": 41886,
        "2023/24": 52186,
        "2024/25": 61627 
    }
    
    # Match periods for display purposes
    MATCH_PERIODS = {
        "1H": "First Half",
        "2H": "Second Half", 
        "ET": "Extra Time",
        "PEN": "Penalties",
        "HT": "Halftime"
    }
    
    # Statistics categories
    STATS_CATEGORIES = {
        "possession": "Ball possession",
        "shots": "Total shots",
        "shots_on_target": "Shots on target",
        "corners": "Corner kicks",
        "fouls": "Fouls",
        "yellow_cards": "Yellow cards",
        "red_cards": "Red cards",
        "offsides": "Offsides",
        "passes": "Total passes",
        "pass_accuracy": "Pass accuracy"
    }

# Legacy support - keep for backward compatibility
class BetType:
    UNKNOWN = "Unknown"

BET_TYPE_MAPPING = {}