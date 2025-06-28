# ai-engine/config/field_mappings.py

from datetime import datetime, date
import requests
import pytz
from dateutil import parser
import logging
from typing import Dict, Any, Optional, Union, Callable
from .core_constants import (
    # SofaScore mappings
    SOFASCORE_POSITION_MAPPING,
    SOFASCORE_STATUS_MAPPING,
    SOFASCORE_OUTCOME_MAPPING,
    SOFASCORE_PLAYER_AVAILABILITY_MAPPING,
    # API-Football mappings
    API_FOOTBALL_POSITION_MAPPING,
    API_FOOTBALL_STATUS_MAPPING,
    API_FOOTBALL_OUTCOME_MAPPING,
    API_FOOTBALL_PLAYER_AVAILABILITY_MAPPING,
    # Unified functions
    get_match_status,
    get_player_position,
    get_match_outcome,
    get_player_availability,
    # Constants
    PlayerAvailabilityStatus,
    PlayerPosition,
    MatchStatus,
    MatchOutcome,
    SofascoreConstants
)
from .settings import get_config

# Hàm helper cho mapping an toàn
logger = logging.getLogger(__name__)

def safe_mapping(mapping: Dict[str, Any], default: Any = None, log_missing: bool = False) -> Callable:
    """Tạo mapper function an toàn với logging"""
    def mapper(value):
        if value is not None and value not in mapping and log_missing:
            logger.warning(f"Missing mapping for '{value}' in {mapping}")
        return mapping.get(value, default)
    return mapper

# =============================================================================
# UNIFIED MAPPERS - Support both SofaScore and API-Football
# =============================================================================

def unified_position_mapper(position: Optional[str], api_type: str = "sofascore") -> str:
    """Unified position mapper cho cả SofaScore và API-Football"""
    return get_player_position(position, api_type)

def unified_status_mapper(status: Optional[str], api_type: str = "sofascore") -> str:
    """Unified status mapper cho cả SofaScore và API-Football"""
    return get_match_status(status, api_type)

def unified_outcome_mapper(outcome: Optional[Union[int, str]], api_type: str = "sofascore") -> str:
    """Unified outcome mapper cho cả SofaScore và API-Football"""
    return get_match_outcome(outcome, api_type)

def unified_player_availability_mapper(status: Optional[str], api_type: str = "sofascore") -> str:
    """Unified player availability mapper cho cả SofaScore và API-Football"""
    return get_player_availability(status, api_type)

# =============================================================================
# LEGACY MAPPERS - Backward compatibility
# =============================================================================

# API-Football legacy mappers
position_mapper = safe_mapping(API_FOOTBALL_POSITION_MAPPING, default=PlayerPosition.UNKNOWN)
status_mapper = safe_mapping(API_FOOTBALL_STATUS_MAPPING, default=MatchStatus.UNKNOWN)
outcome_mapper = safe_mapping(API_FOOTBALL_OUTCOME_MAPPING, default=MatchOutcome.UNKNOWN)
player_status_mapper = safe_mapping(API_FOOTBALL_PLAYER_AVAILABILITY_MAPPING, default=PlayerAvailabilityStatus.UNKNOWN)

# SofaScore specific mappers
sofascore_position_mapper = safe_mapping(SOFASCORE_POSITION_MAPPING, default=PlayerPosition.UNKNOWN)
sofascore_status_mapper = safe_mapping(SOFASCORE_STATUS_MAPPING, default=MatchStatus.UNKNOWN)
sofascore_outcome_mapper = safe_mapping(SOFASCORE_OUTCOME_MAPPING, default=MatchOutcome.UNKNOWN)
sofascore_player_status_mapper = safe_mapping(SOFASCORE_PLAYER_AVAILABILITY_MAPPING, default=PlayerAvailabilityStatus.UNKNOWN)

# =============================================================================
# EVENT TYPE MAPPINGS - Enhanced for both APIs
# =============================================================================

# API-Football event types
API_FOOTBALL_EVENT_MAPPING = {
    # Goals
    "Goal": "goal",
    "Normal Goal": "goal",
    "Own Goal": "own_goal",
    "Penalty": "penalty_goal",
    "Missed Penalty": "missed_penalty",
    # Cards
    "Yellow Card": "yellow_card",
    "Red Card": "red_card",
    # Substitution
    "Subst": "substitution",
    # VAR
    "Var": "var_decision",
    "Goal cancelled": "goal_cancelled",
    "Penalty confirmed": "penalty_confirmed"
}

# SofaScore event types
SOFASCORE_EVENT_MAPPING = {
    # Goals
    "goal": "goal",
    "ownGoal": "own_goal",
    "penalty": "penalty_goal",
    "penaltyMissed": "missed_penalty",
    # Cards
    "yellowCard": "yellow_card",
    "redCard": "red_card",
    "secondYellow": "red_card",
    # Substitution
    "substitution": "substitution",
    # VAR
    "varDecision": "var_decision",
    "goalCancelled": "goal_cancelled",
    "penaltyAwarded": "penalty_confirmed",
    # Injuries and other events
    "injury": "injury",
    "cornerKick": "corner_kick",
    "freeKick": "free_kick",
    "offside": "offside"
}

def unified_event_type_mapper(event_type: Optional[str], api_type: str = "sofascore") -> str:
    """Unified event type mapper"""
    if not event_type:
        return "unknown"
    
    if api_type == "sofascore":
        return SOFASCORE_EVENT_MAPPING.get(event_type, "unknown")
    else:  # api_football
        return API_FOOTBALL_EVENT_MAPPING.get(event_type, "unknown")

# Legacy mapper for backward compatibility
event_type_mapper = safe_mapping(API_FOOTBALL_EVENT_MAPPING, default="unknown")

# =============================================================================
# PERIOD MAPPINGS - Enhanced for both APIs
# =============================================================================

# API-Football period mapping
API_FOOTBALL_PERIOD_MAPPING = {
    "1H": "first_half",
    "2H": "second_half",
    "HT": "halftime",
    "ET": "extra_time",
    "P": "penalty_shootout",
    "BT": "break_time"
}

# SofaScore period mapping
SOFASCORE_PERIOD_MAPPING = {
    "1": "first_half",
    "2": "second_half",
    "3": "extra_time_first",
    "4": "extra_time_second",
    "5": "penalty_shootout",
    "halftime": "halftime",
    "pause": "break_time"
}

def unified_period_mapper(period: Optional[Union[str, int]], api_type: str = "sofascore") -> str:
    """Unified period mapper"""
    if period is None:
        return "unknown"
    
    period_str = str(period)
    if api_type == "sofascore":
        return SOFASCORE_PERIOD_MAPPING.get(period_str, "unknown")
    else:  # api_football
        return API_FOOTBALL_PERIOD_MAPPING.get(period_str, "unknown")

# Legacy mapper
period_mapper = safe_mapping(API_FOOTBALL_PERIOD_MAPPING, default="unknown")

# =============================================================================
# LOCATION MAPPINGS
# =============================================================================

LOCATION_MAPPING = {
    "home": "home",
    "away": "away",
    "total": "overall",
    "overall": "overall"
}
location_mapper = safe_mapping(LOCATION_MAPPING, default="overall")

# =============================================================================
# CARD MAPPINGS
# =============================================================================

CARD_MAPPING = {
    "yellow": "yellow_cards",
    "red": "red_cards",
    "yellowCard": "yellow_cards",
    "redCard": "red_cards"
}
card_mapper = safe_mapping(CARD_MAPPING, default=None)

# =============================================================================
# BOOKMAKER MAPPINGS
# =============================================================================

def load_bookmaker_mapping() -> Dict[int, str]:
    """
    Load bookmaker mapping from API-Football.
    Falls back to empty dict if API is not available.
    """
    try:
        config = get_config()
        if not hasattr(config, 'api_football') or not config.api_football.is_configured:
            logger.warning("API-Football not configured, skipping bookmaker mapping")
            return {}
            
        url = f"{config.api_football.base_url}/odds/bookmakers"
        headers = {
            "x-rapidapi-host": str(config.api_football.base_url).split('://')[-1],
            "x-rapidapi-key": config.api_football.get_random_key()
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("response", [])
        return {int(item["id"]): item["name"] for item in data if "id" in item and "name" in item}
        
    except Exception as e:
        logger.error(f"Failed to load bookmaker mapping: {e}")
        return {}

# Lazy loading để tránh lỗi khi config chưa sẵn sàng
_bookmaker_mapping: Optional[Dict[int, str]] = None

def get_bookmaker_mapping() -> Dict[int, str]:
    """Get bookmaker mapping with caching"""
    global _bookmaker_mapping
    if _bookmaker_mapping is None:
        _bookmaker_mapping = load_bookmaker_mapping()
    return _bookmaker_mapping

def bookmaker_mapper(bookmaker_id: Optional[Union[int, str]]) -> str:
    """Map bookmaker ID to name"""
    if bookmaker_id is None:
        return "Unknown"
    
    try:
        mapping = get_bookmaker_mapping()
        return mapping.get(int(bookmaker_id), "Unknown")
    except (ValueError, TypeError):
        return "Unknown"

# =============================================================================
# FIELD MAPPINGS - Enhanced for both APIs
# =============================================================================

# API-Football field mapping
API_FOOTBALL_FIELD_MAPPING = {
    # League and Country
    "league.id": "league_id",
    "league.name": "league_name",
    "league.country": "league_country",
    # Team
    "team.id": "team_id",
    "team.name": "team_name",
    # Venue
    "venue.id": "venue_id",
    "venue.name": "venue_name",
    "venue.city": "venue_city",
    "venue.capacity": "venue_capacity",
    # Player
    "player.id": "player_id",
    "player.name": "player_name",
    "player.birth.date": "date_of_birth",
    "player.nationality": "nationality",
    # Fixture
    "fixture.id": "fixture_id",
    "fixture.date": "fixture_datetime",
    "fixture.status.short": "status_code",
    # Teams in fixture
    "teams.home.id": "home_team_id",
    "teams.away.id": "away_team_id",
    # Score
    "goals.home": "home_goals",
    "goals.away": "away_goals",
    "score.halftime.home": "half_time_home_goals",
    "score.halftime.away": "half_time_away_goals",
    # Player stats
    "games.minutes": "minutes_played",
    "goals.total": "goals",
    "goals.assists": "assists",
    "shots.total": "shots_total",
    "shots.on": "shots_on",
    "passes.total": "passes_total",
    "passes.accuracy": "passes_accuracy",
    "tackles.total": "tackles",
    "duels.won": "duels_won",
    "fouls.committed": "fouls_committed",
    # Cards
    "cards.yellow": "yellow_cards",
    "cards.red": "red_cards",
    # Team stats extras
    "statistics.ball_possession": "possession_percent",
    "statistics.corner_kicks": "corner_kicks",
    "statistics.offsides": "offsides",
    # Odds and betting
    "odds.bookmaker_id": "bookmaker_id",
    "odds.bet_id": "bet_id",
    "odds.value": "bet_value",
    "odds.odd": "odd"
}

# SofaScore field mapping
SOFASCORE_FIELD_MAPPING = {
    # Tournament and Season
    "tournament.id": "league_id",
    "tournament.name": "league_name",
    "tournament.category.name": "league_country",
    "season.id": "season_id",
    "season.name": "season_name",
    # Team
    "homeTeam.id": "home_team_id",
    "homeTeam.name": "home_team_name",
    "awayTeam.id": "away_team_id",
    "awayTeam.name": "away_team_name",
    # Match
    "id": "match_id",
    "startTimestamp": "match_timestamp",
    "status.code": "status_code",
    "status.description": "status_description",
    # Score
    "homeScore.current": "home_goals",
    "awayScore.current": "away_goals",
    "homeScore.period1": "half_time_home_goals",
    "awayScore.period1": "half_time_away_goals",
    # Player
    "player.id": "player_id",
    "player.name": "player_name",
    "player.dateOfBirthTimestamp": "date_of_birth_timestamp",
    "player.country.name": "nationality",
    "player.position": "position_code",
    # Statistics
    "statistics.goals": "goals",
    "statistics.assists": "assists",
    "statistics.minutesPlayed": "minutes_played",
    "statistics.totalShots": "shots_total",
    "statistics.shotsOnTarget": "shots_on",
    "statistics.totalPasses": "passes_total",
    "statistics.accuratePasses": "passes_accurate",
    "statistics.passAccuracy": "passes_accuracy",
    "statistics.tackles": "tackles",
    "statistics.duelsWon": "duels_won",
    "statistics.foulsCommitted": "fouls_committed",
    "statistics.yellowCards": "yellow_cards",
    "statistics.redCards": "red_cards",
    # Team statistics
    "statistics.ballPossession": "possession_percent",
    "statistics.cornerKicks": "corner_kicks",
    "statistics.offsides": "offsides",
    # Venue
    "venue.id": "venue_id",
    "venue.stadium.name": "venue_name",
    "venue.stadium.capacity": "venue_capacity",
    "venue.city.name": "venue_city"
}

def get_field_mapping(api_type: str = "sofascore") -> Dict[str, str]:
    """Get field mapping for specified API"""
    if api_type == "sofascore":
        return SOFASCORE_FIELD_MAPPING
    else:  # api_football
        return API_FOOTBALL_FIELD_MAPPING

# Legacy mapping for backward compatibility
FIELD_MAPPING = API_FOOTBALL_FIELD_MAPPING

# =============================================================================
# CONVERSION FUNCTIONS - Enhanced
# =============================================================================

def convert_birthdate(birth_input: Union[str, int, None]) -> Optional[date]:
    """Convert birth date from string or timestamp to date object"""
    if not birth_input:
        return None
    
    try:
        # Handle timestamp (SofaScore format)
        if isinstance(birth_input, (int, float)):
            return datetime.fromtimestamp(birth_input, tz=pytz.UTC).date()
        
        # Handle string (API-Football format)
        if isinstance(birth_input, str):
            return parser.isoparse(birth_input).date()
            
    except (ValueError, TypeError, OSError) as e:
        logger.warning(f"Failed to convert birthdate '{birth_input}': {e}")
        return None
    
    return None

def convert_accuracy(value: Union[str, int, float, None]) -> Optional[float]:
    """Convert accuracy from % or number to float"""
    if value is None:
        return None
    
    try:
        if isinstance(value, str) and value.endswith('%'):
            return float(value.rstrip('%')) / 100
        return float(value)
    except (TypeError, ValueError):
        return None

def convert_datetime(dt_input: Union[str, int, None]) -> Optional[datetime]:
    """Convert datetime string or timestamp to UTC datetime object"""
    if not dt_input:
        return None
    
    try:
        # Handle timestamp (SofaScore format)
        if isinstance(dt_input, (int, float)):
            return datetime.fromtimestamp(dt_input, tz=pytz.UTC)
        
        # Handle string (API-Football format)
        if isinstance(dt_input, str):
            dt = parser.isoparse(dt_input)
            return dt.astimezone(pytz.UTC)
            
    except (ValueError, TypeError, OSError) as e:
        logger.warning(f"Failed to convert datetime '{dt_input}': {e}")
        return None
    
    return None

def convert_timestamp_to_date(timestamp: Union[int, None]) -> Optional[date]:
    """Convert timestamp to date (for SofaScore birth dates)"""
    if not timestamp:
        return None
    
    try:
        return datetime.fromtimestamp(timestamp, tz=pytz.UTC).date()
    except (OSError, ValueError, TypeError):
        return None

def convert_possession_percent(value: Union[str, int, float, None]) -> Optional[float]:
    """Convert possession percentage to float"""
    if value is None:
        return None
    
    try:
        if isinstance(value, str):
            # Remove % sign if present
            value = value.rstrip('%')
        
        result = float(value)
        # Ensure it's a valid percentage (0-100)
        return max(0.0, min(100.0, result))
    except (TypeError, ValueError):
        return None

# =============================================================================
# SPECIAL CONVERSIONS - Enhanced for both APIs
# =============================================================================

# API-Football special conversions
API_FOOTBALL_SPECIAL_CONVERSIONS = {
    "player.birth.date": convert_birthdate,
    "passes.accuracy": convert_accuracy,
    "statistics.pass_accuracy%": convert_accuracy,
    "fixture.date": convert_datetime,
    "statistics.ball_possession": convert_possession_percent
}

# SofaScore special conversions
SOFASCORE_SPECIAL_CONVERSIONS = {
    "player.dateOfBirthTimestamp": convert_timestamp_to_date,
    "startTimestamp": convert_datetime,
    "statistics.passAccuracy": convert_accuracy,
    "statistics.ballPossession": convert_possession_percent
}

def get_special_conversions(api_type: str = "sofascore") -> Dict[str, Callable]:
    """Get special conversions for specified API"""
    if api_type == "sofascore":
        return SOFASCORE_SPECIAL_CONVERSIONS
    else:  # api_football
        return API_FOOTBALL_SPECIAL_CONVERSIONS

# Legacy for backward compatibility
SPECIAL_CONVERSIONS = API_FOOTBALL_SPECIAL_CONVERSIONS

# =============================================================================
# ENDPOINT CONFIGURATIONS
# =============================================================================

# API-Football paginated endpoints
API_FOOTBALL_PAGINATED_ENDPOINTS = [
    "players", "fixtures", "teams", "transfers", 
    "injuries", "trophies", "sidelined", "odds"
]

# SofaScore endpoints that support pagination
SOFASCORE_PAGINATED_ENDPOINTS = [
    "events", "players", "seasons", "tournaments", "statistics"
]

def get_paginated_endpoints(api_type: str = "sofascore") -> list:
    """Get paginated endpoints for specified API"""
    if api_type == "sofascore":
        return SOFASCORE_PAGINATED_ENDPOINTS
    else:  # api_football
        return API_FOOTBALL_PAGINATED_ENDPOINTS

# Legacy
PAGINATED_ENDPOINTS = API_FOOTBALL_PAGINATED_ENDPOINTS

# =============================================================================
# DEFAULT VALUES AND CONSTANTS
# =============================================================================

# Timezone constants
DEFAULT_TIMEZONE = "UTC"
UK_TIMEZONE = "Europe/London"

# Default values for player statistics
DEFAULT_PLAYER_STATS = {
    "minutes_played": 0,
    "goals": 0,
    "assists": 0,
    "shots_total": 0,
    "shots_on": 0,
    "passes_total": 0,
    "passes_accurate": 0,
    "passes_accuracy": 0.0,
    "tackles": 0,
    "duels_won": 0,
    "fouls_committed": 0,
    "yellow_cards": 0,
    "red_cards": 0,
    "possession_percent": 0.0,
    "corner_kicks": 0,
    "offsides": 0
}

# Default values for team statistics
DEFAULT_TEAM_STATS = {
    "matches_played": 0,
    "wins": 0,
    "draws": 0,
    "losses": 0,
    "goals_for": 0,
    "goals_against": 0,
    "goal_difference": 0,
    "points": 0,
    "clean_sheets": 0,
    "failed_to_score": 0
}

# Legacy compatibility
DEFAULT_VALUES = DEFAULT_PLAYER_STATS

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_default_value(field_name: str, api_type: str = "sofascore") -> Any:
    """Get default value for a field"""
    return DEFAULT_PLAYER_STATS.get(field_name, None)

def normalize_team_name(name: str) -> str:
    """Normalize team name for consistency"""
    if not name:
        return ""
    
    # Common team name normalizations
    normalizations = {
        "Manchester United": "Manchester Utd",
        "Manchester City": "Manchester City",
        "Tottenham Hotspur": "Tottenham",
        "Newcastle United": "Newcastle",
        "West Ham United": "West Ham",
        "Brighton & Hove Albion": "Brighton",
        "Wolverhampton Wanderers": "Wolves"
    }
    
    return normalizations.get(name, name)

def extract_season_from_name(season_name: str) -> Optional[int]:
    """Extract start year from season name (e.g., '2023/24' -> 2023)"""
    if not season_name:
        return None
    
    try:
        # Handle formats like "2023/24", "2023-24", "2023/2024"
        if '/' in season_name:
            return int(season_name.split('/')[0])
        elif '-' in season_name:
            return int(season_name.split('-')[0])
        else:
            # Try to parse as year directly
            return int(season_name)
    except (ValueError, IndexError):
        return None

def build_sofascore_url(endpoint: str, **params) -> str:
    """Build SofaScore API URL with parameters"""
    try:
        config = get_config()
        base_url = str(config.sofascore.base_url).rstrip('/')
        
        if params:
            param_str = "&".join([f"{k}={v}" for k, v in params.items() if v is not None])
            return f"{base_url}/{endpoint}?{param_str}"
        else:
            return f"{base_url}/{endpoint}"
    except Exception:
        return f"https://api.sofascore.com/api/v1/{endpoint}"

def build_api_football_url(endpoint: str, **params) -> str:
    """Build API-Football URL with parameters"""
    try:
        config = get_config()
        base_url = str(config.api_football.base_url).rstrip('/')
        
        if params:
            param_str = "&".join([f"{k}={v}" for k, v in params.items() if v is not None])
            return f"{base_url}/{endpoint}?{param_str}"
        else:
            return f"{base_url}/{endpoint}"
    except Exception:
        return f"https://v3.football.api-sports.io/{endpoint}"