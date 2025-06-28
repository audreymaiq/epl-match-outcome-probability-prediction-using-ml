# ai-engine/config/core_constants.py

from typing import Optional, Dict, Union

class MatchStatus:
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"
    ABANDONED = "ABANDONED"
    UNKNOWN = "UNKNOWN"

# SofaScore status mapping (khác với API-Football)
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

# Legacy API-Football mapping (kept for reference/migration)
# Keys normalized to uppercase for consistency
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

class PlayerPosition:
    GK = "GK"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"
    UNKNOWN = "UNKNOWN"

# SofaScore position mapping - keys normalized to lowercase
SOFASCORE_POSITION_MAPPING = {
    "g": PlayerPosition.GK,      # Goalkeeper
    "d": PlayerPosition.DEF,     # Defender
    "m": PlayerPosition.MID,     # Midfielder
    "f": PlayerPosition.FWD,     # Forward
    
    # Full names từ SofaScore - normalized to lowercase
    "goalkeeper": PlayerPosition.GK,
    "defender": PlayerPosition.DEF,
    "midfielder": PlayerPosition.MID,
    "forward": PlayerPosition.FWD,
    "attacker": PlayerPosition.FWD
}

# Legacy API-Football position mapping - keys normalized to lowercase
API_FOOTBALL_POSITION_MAPPING = {
    "goalkeeper": PlayerPosition.GK,
    "defender": PlayerPosition.DEF,
    "midfielder": PlayerPosition.MID,
    "attacker": PlayerPosition.FWD
}

class MatchOutcome:
    HOME = "H"
    DRAW = "D"
    AWAY = "A"
    UNKNOWN = "UNKNOWN"

class SofascoreWinnerCodes:
    """SofaScore winner code constants"""
    HOME_WIN = 1
    AWAY_WIN = 2
    DRAW = 3

# SofaScore outcome mapping - keys normalized to string
SOFASCORE_OUTCOME_MAPPING = {
    # Numeric codes as strings
    "1": MatchOutcome.HOME,    # Home team wins
    "2": MatchOutcome.AWAY,    # Away team wins
    "3": MatchOutcome.DRAW,    # Draw
    
    # Text-based (backup)
    "home": MatchOutcome.HOME,
    "away": MatchOutcome.AWAY,
    "draw": MatchOutcome.DRAW
}

# Legacy API-Football outcome mapping - keys normalized to lowercase
API_FOOTBALL_OUTCOME_MAPPING = {
    "home": MatchOutcome.HOME,
    "draw": MatchOutcome.DRAW,
    "away": MatchOutcome.AWAY
}

class PlayerAvailabilityStatus:
    MISSING = "Missing Fixture"
    QUESTIONABLE = "Questionable"
    INJURED = "Injured"
    SUSPENDED = "Suspended"
    UNKNOWN = "Unknown"

# SofaScore player availability mapping
SOFASCORE_PLAYER_AVAILABILITY_MAPPING = {
    "missing": PlayerAvailabilityStatus.MISSING,
    "questionable": PlayerAvailabilityStatus.QUESTIONABLE,
    "injured": PlayerAvailabilityStatus.INJURED,
    "suspended": PlayerAvailabilityStatus.SUSPENDED,
    "doubt": PlayerAvailabilityStatus.QUESTIONABLE
}

# Legacy API-Football player availability mapping
API_FOOTBALL_PLAYER_AVAILABILITY_MAPPING = {
    "missing fixture": PlayerAvailabilityStatus.MISSING,
    "questionable": PlayerAvailabilityStatus.QUESTIONABLE
}

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

# Unified mapping functions for easy switching between APIs
def get_match_status(api_status: Optional[str], api_type: str = "sofascore") -> str:
    """
    Get unified match status from API-specific status
    
    Args:
        api_status: Status from API
        api_type: "sofascore" or "api_football"
    
    Returns:
        Unified MatchStatus
    """
    if not isinstance(api_status, str):
        return MatchStatus.UNKNOWN
        
    if api_type == "sofascore":
        return SOFASCORE_STATUS_MAPPING.get(api_status.lower(), MatchStatus.UNKNOWN)
    elif api_type == "api_football":
        return API_FOOTBALL_STATUS_MAPPING.get(api_status.upper(), MatchStatus.UNKNOWN)
    else:
        return MatchStatus.UNKNOWN

def get_player_position(api_position: Optional[str], api_type: str = "sofascore") -> str:
    """
    Get unified player position from API-specific position
    
    Args:
        api_position: Position from API
        api_type: "sofascore" or "api_football"
    
    Returns:
        Unified PlayerPosition
    """
    if not isinstance(api_position, str):
        return PlayerPosition.UNKNOWN
        
    if api_type == "sofascore":
        return SOFASCORE_POSITION_MAPPING.get(api_position.lower(), PlayerPosition.UNKNOWN)
    elif api_type == "api_football":
        return API_FOOTBALL_POSITION_MAPPING.get(api_position.lower(), PlayerPosition.UNKNOWN)
    else:
        return PlayerPosition.UNKNOWN

def get_match_outcome(api_outcome: Optional[Union[int, str]], api_type: str = "sofascore") -> str:
    """
    Get unified match outcome from API-specific outcome
    
    Args:
        api_outcome: Outcome from API (can be int, str)
        api_type: "sofascore" or "api_football"
    
    Returns:
        Unified MatchOutcome
    """
    if api_outcome is None:
        return MatchOutcome.UNKNOWN
        
    # Normalize input to string and lowercase
    normalized_outcome = str(api_outcome).lower()
    
    if api_type == "sofascore":
        return SOFASCORE_OUTCOME_MAPPING.get(normalized_outcome, MatchOutcome.UNKNOWN)
    elif api_type == "api_football":
        return API_FOOTBALL_OUTCOME_MAPPING.get(normalized_outcome, MatchOutcome.UNKNOWN)
    else:
        return MatchOutcome.UNKNOWN

def get_player_availability(api_status: Optional[str], api_type: str = "sofascore") -> str:
    """
    Get unified player availability status from API-specific status
    
    Args:
        api_status: Availability status from API
        api_type: "sofascore" or "api_football"
    
    Returns:
        Unified PlayerAvailabilityStatus
    """
    if not isinstance(api_status, str):
        return PlayerAvailabilityStatus.UNKNOWN
        
    normalized_status = api_status.lower()
    
    if api_type == "sofascore":
        return SOFASCORE_PLAYER_AVAILABILITY_MAPPING.get(normalized_status, PlayerAvailabilityStatus.UNKNOWN)
    elif api_type == "api_football":
        return API_FOOTBALL_PLAYER_AVAILABILITY_MAPPING.get(normalized_status, PlayerAvailabilityStatus.UNKNOWN)
    else:
        return PlayerAvailabilityStatus.UNKNOWN

# Legacy support - keep for backward compatibility
class BetType:
    UNKNOWN = "Unknown"

BET_TYPE_MAPPING = {}