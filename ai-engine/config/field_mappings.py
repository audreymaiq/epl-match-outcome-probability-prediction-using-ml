# # ai-engine/config/field_mappings.py

# from datetime import datetime, date, timedelta
# import requests
# import pytz
# from dateutil import parser
# import logging
# from typing import Dict, Any, Optional, Union, Callable
# from .core_constants import MatchStatus, PlayerPosition, MatchOutcome, PlayerStatus, MatchEventType, MatchPeriod
# from .settings import get_config


# # Hàm helper cho mapping an toàn
# logger = logging.getLogger(__name__)

# def safe_mapping(mapping: Dict[str, Any], default: Any = None, log_missing: bool = False) -> Callable:
#     """Tạo mapper function an toàn với logging"""
#     def mapper(value):
#         if value is not None and value not in mapping and log_missing:
#             logger.warning(f"Missing mapping for '{value}' in {mapping}")
#         return mapping.get(value, default)
#     return mapper

# # UNIFIED MAPPERS - Support both SofaScore and API-Football

# def unified_position_mapper(position: Optional[str], api_type: str = "sofascore") -> str:
#     """Unified position mapper cho cả SofaScore và API-Football"""
#     return get_player_position(position, api_type)

# def unified_status_mapper(status: Optional[str], api_type: str = "sofascore") -> str:
#     """Unified status mapper cho cả SofaScore và API-Football"""
#     return get_match_status(status, api_type)

# def unified_outcome_mapper(outcome: Optional[Union[int, str]], api_type: str = "sofascore") -> str:
#     """Unified outcome mapper cho cả SofaScore và API-Football"""
#     return get_match_outcome(outcome, api_type)

# def unified_player_availability_mapper(status: Optional[str], api_type: str = "sofascore") -> str:
#     """Unified player availability mapper cho cả SofaScore và API-Football"""
#     return get_player_availability(status, api_type)

# def unified_event_type_mapper(event_type: Optional[str], api_type: str = "sofascore") -> str:
#     """Unified event type mapper"""
#     if not event_type:
#         return None
    
#     if api_type == "sofascore":
#         return SOFASCORE_EVENT_MAPPING.get(event_type)
#     else:  # api_football
#         return API_FOOTBALL_EVENT_MAPPING.get(event_type)

# def unified_period_mapper(period: Optional[Union[str, int]], api_type: str = "sofascore") -> str:
#     """Unified period mapper"""
#     if period is None:
#         return None
    
#     period_str = str(period)
#     if api_type == "sofascore":
#         return SOFASCORE_PERIOD_MAPPING.get(period_str)
#     else:  # api_football
#         return API_FOOTBALL_PERIOD_MAPPING.get(period_str)

# def unified_match_status_mapper(status: Optional[str], api_type: str = "sofascore") -> Optional[MatchStatus]:
#     """Unified status mapper."""
#     return get_match_status(status, api_type)

# def unified_match_outcome_mapper(outcome: Optional[Union[int, str]], api_type: str = "sofascore") -> Optional[MatchOutcome]:
#     """Unified outcome mapper."""
#     return get_match_outcome(outcome, api_type)


# # =============================================================================
# # EVENT TYPE MAPPINGS 

# # API-Football event types
# API_FOOTBALL_EVENT_MAPPING = {
#     # Goals
#     "Goal": "goal",
#     "Normal Goal": "goal",
#     "Own Goal": "own_goal",
#     "Penalty": "penalty_goal",
#     "Missed Penalty": "missed_penalty",
#     # Cards
#     "Yellow Card": "yellow card",
#     "Red Card": "red card",
#     # Substitution
#     "Subst": "substitution",
#     # VAR
#     "Var": "var_decision",
#     "Goal cancelled": "goal_cancelled",
#     "Penalty confirmed": "penalty_confirmed"
# }

# # SofaScore event types
# SOFASCORE_EVENT_MAPPING = {
#     # Goals
#     "goal": "goal",
#     "ownGoal": "own_goal",
#     "penalty": "penalty_goal",
#     "penaltyMissed": "missed_penalty",
#     # Cards
#     "yellowCard": "yellow card",
#     "redCard": "red card",
#     "secondYellow": "red card",
#     # Substitution
#     "substitution": "substitution",
#     # VAR
#     "varDecision": "var_decision",
#     "goalCancelled": "goal_cancelled",
#     "penaltyAwarded": "penalty_confirmed",
#     # Injuries and other events
#     "injury": "injury",
#     "cornerKick": "corner_kick",
#     "freeKick": "free_kick",
#     "offside": "offside"
# }

# # Legacy mapper for backward compatibility
# event_type_mapper = safe_mapping(API_FOOTBALL_EVENT_MAPPING, default=None)

# # =============================================================================
# # PERIOD MAPPINGS 

# # API-Football period mapping
# API_FOOTBALL_PERIOD_MAPPING = {
#     "1H": "1H",
#     "2H": "2H",
#     "ET": "ET1", 
#     "P": "PEN"
# }

# # SofaScore period mapping
# SOFASCORE_PERIOD_MAPPING = {
#     "1": "1H",
#     "2": "2H",
#     "3": "ET1", 
#     "4": "ET2", 
#     "5": "PEN"
# }

# # Legacy mapper
# period_mapper = safe_mapping(API_FOOTBALL_PERIOD_MAPPING, default=None)

# # =============================================================================
# # LOCATION MAPPINGS

# LOCATION_MAPPING = {
#     "home": "Home",
#     "away": "Away",
#     "total": "Overall",
#     "overall": "Overall"
# }
# location_mapper = safe_mapping(LOCATION_MAPPING, default="Overall")

# # =============================================================================
# # CARD MAPPINGS

# CARD_MAPPING = {
#     "yellow": "yellow_cards",
#     "red": "red_cards",
#     "yellowCard": "yellow_cards",
#     "redCard": "red_cards"
# }
# card_mapper = safe_mapping(CARD_MAPPING, default=None)

# # =============================================================================
# # BOOKMAKER MAPPINGS

# def load_bookmaker_mapping() -> Dict[int, str]:
#     """
#     Load bookmaker mapping from API-Football.
#     Falls back to empty dict if API is not available.
#     """
#     try:
#         config = get_config()
#         if not hasattr(config, 'api_football') or not config.api_football.is_configured:
#             logger.warning("API-Football not configured, skipping bookmaker mapping")
#             return {}
            
#         url = f"{config.api_football.base_url}/odds/bookmakers"
#         headers = {
#             "x-rapidapi-host": str(config.api_football.base_url).split('://')[-1],
#             "x-rapidapi-key": config.api_football.get_random_key()
#         }
        
#         resp = requests.get(url, headers=headers, timeout=10)
#         resp.raise_for_status()
#         data = resp.json().get("response", [])
#         return {int(item["id"]): item["name"] for item in data if "id" in item and "name" in item}
        
#     except Exception as e:
#         logger.error(f"Failed to load bookmaker mapping: {e}")
#         return {}

# # Lazy loading để tránh lỗi khi config chưa sẵn sàng
# _bookmaker_mapping: Optional[Dict[int, str]] = None

# def get_bookmaker_mapping() -> Dict[int, str]:
#     """Get bookmaker mapping with caching"""
#     global _bookmaker_mapping
#     if _bookmaker_mapping is None:
#         _bookmaker_mapping = load_bookmaker_mapping()
#     return _bookmaker_mapping

# def bookmaker_mapper(bookmaker_id: Optional[Union[int, str]]) -> str:
#     """Map bookmaker ID to name"""
#     if bookmaker_id is None:
#         return "Unknown"
    
#     try:
#         mapping = get_bookmaker_mapping()
#         return mapping.get(int(bookmaker_id), "Unknown")
#     except (ValueError, TypeError):
#         return "Unknown"

# # =============================================================================
# # FIELD MAPPINGS 

# # API-Football field mapping
# API_FOOTBALL_FIELD_MAPPING = {
#     # League and Country
#     "league.id": "league_id",
#     "league.name": "league_name",
#     "league.country": "league_country",
#     # Team
#     "team.id": "team_id",
#     "team.name": "team_name",
#     # Venue
#     "venue.id": "venue_id",
#     "venue.name": "venue_name",
#     "venue.city": "venue_city",
#     "venue.capacity": "venue_capacity",
#     # Player
#     "player.id": "player_id",
#     "player.name": "player_name",
#     "player.birth.date": "date_of_birth",
#     "player.nationality": "nationality",
#     # Fixture
#     "fixture.id": "fixture_id",
#     "fixture.date": "fixture_datetime",
#     "fixture.status.short": "status_code",
#     # Teams in fixture
#     "teams.home.id": "home_team_id",
#     "teams.away.id": "away_team_id",
#     # Score
#     "goals.home": "home_goals",
#     "goals.away": "away_goals",
#     "score.halftime.home": "half_time_home_goals",
#     "score.halftime.away": "half_time_away_goals",
#     # Player stats
#     "games.minutes": "minutes_played",
#     "goals.total": "goals",
#     "goals.assists": "assists",
#     "shots.total": "shots",
#     "shots.on": "shots_on_target",
#     "passes.total": "passes",
#     "passes.accuracy": "passes_accuracy",
#     "tackles.total": "tackles",
#     "duels.won": "duels_won",
#     "fouls.committed": "fouls_committed",
#     # Cards
#     "cards.yellow": "yellow_cards",
#     "cards.red": "red_cards",
#     # Team stats extras
#     "statistics.ball_possession": "possession_percent",
#     "statistics.corner_kicks": "corner_kicks",
#     "statistics.offsides": "offsides",
#     # Odds and betting
#     "odds.bookmaker_id": "bookmaker_id",
#     "odds.bet_id": "bet_id",
#     "odds.value": "bet_value",
#     "odds.odd": "odd"
# }

# # SofaScore field mapping
# SOFASCORE_FIELD_MAPPING = {
#     # ========== Tournament and Season ==========
#     "tournament.id": "league_id",
#     "tournament.name": "league_name",
#     "tournament.category.name": "league_country",
#     "tournament.uniqueTournament.id": "unique_tournament_id",
#     "tournament.priority": "tournament_priority",
#     "season.id": "season_id",
#     "season.name": "season_name",
#     "season.year": "season_year_str",

#     # ========== Match Core & Metadata ==========
#     "id": "match_id",
#     "startTimestamp": "match_timestamp",
#     "status.description": "status_description",
#     "roundInfo.round": "round",
#     "winnerCode": "outcome_code",
#     "attendance": "attendance",
#     "hasXg": "has_xg",
#     "hasEventPlayerStatistics": "has_event_player_statistics",

#     # ========== Score Details ==========
#     "homeScore.period1": "half_time_home_goals",
#     "awayScore.period1": "half_time_away_goals",
#     "homeScore.normaltime": "home_goals_normaltime",
#     "awayScore.normaltime": "away_goals_normaltime",

#     # ========== Time Details ==========
#     "time.injuryTime1": "injury_time_first_half",
#     "time.injuryTime2": "injury_time_second_half",

#     # ========== Home Team ==========
#     "homeTeam.id": "home_team_id",
#     "homeTeam.name": "home_team_name",
#     "homeTeam.shortName": "home_team_short_name",
#     "homeTeam.nameCode": "home_team_code",
#     "homeTeam.fullName": "home_team_full_name",
#     "homeTeam.foundationDateTimestamp": "home_team_established_ts",
#     "homeTeam.userCount": "home_team_fan_count",
#     "homeTeam.manager.name": "home_team_manager_name",
#     "homeTeam.manager.id": "home_team_manager_id",
#     "homeTeam.manager.country.name": "home_team_manager_country",
#     "homeTeam.venue.id": "home_team_venue_id",
#     "homeTeam.venue.name": "home_team_venue_name",
#     "homeTeam.venue.city.name": "home_team_venue_city",
#     "homeTeam.venue.capacity": "home_team_venue_capacity",
#     "homeTeam.venue.venueCoordinates.latitude": "home_team_venue_latitude",
#     "homeTeam.venue.venueCoordinates.longitude": "home_team_venue_longitude",    
#     "homeTeam.teamColors.primary": "home_team_primary_color",
#     "homeTeam.teamColors.secondary": "home_team_secondary_color",
    
#     # ========== Away Team ==========
#     "awayTeam.id": "away_team_id",
#     "awayTeam.name": "away_team_name",
#     "awayTeam.shortName": "away_team_short_name",
#     "awayTeam.nameCode": "away_team_code",
#     "awayTeam.fullName": "away_team_full_name",
#     "awayTeam.foundationDateTimestamp": "away_team_established_ts",
#     "awayTeam.userCount": "away_team_fan_count",
#     "awayTeam.manager.name": "away_team_manager_name",
#     "awayTeam.manager.id": "away_team_manager_id",
#     "awayTeam.manager.country.name": "away_team_manager_country",
#     "awayTeam.venue.id": "away_team_venue_id",
#     "awayTeam.venue.name": "away_team_venue_name",
#     "awayTeam.venue.city.name": "away_team_venue_city",
#     "awayTeam.venue.capacity": "away_team_venue_capacity",
#     "awayTeam.venue.venueCoordinates.latitude": "away_team_venue_latitude",
#     "awayTeam.venue.venueCoordinates.longitude": "away_team_venue_longitude",
#     "awayTeam.teamColors.primary": "away_team_primary_color",
#     "awayTeam.teamColors.secondary": "away_team_secondary_color",
    
#     # ========== Match Venue ==========
#     "venue.id": "match_venue_id",
#     "venue.name": "match_venue_name",
#     "venue.city.name": "match_venue_city",
#     "venue.capacity": "match_venue_capacity",
#     "venue.venueCoordinates.latitude": "match_venue_latitude",
#     "venue.venueCoordinates.longitude": "match_venue_longitude",

#     # ========== Referee ==========
#     "referee.id": "referee_id",
#     "referee.name": "referee_name",
#     "referee.country.name": "referee_country",
#     "referee.yellowCards": "referee_total_yellow_cards",
#     "referee.redCards": "referee_total_red_cards",
#     "referee.yellowRedCards": "referee_total_yellow_red_cards",
#     "referee.games": "referee_total_games",
# }

# def get_field_mapping(api_type: str = "sofascore") -> Dict[str, str]:
#     """Get field mapping for specified API"""
#     if api_type == "sofascore":
#         return SOFASCORE_FIELD_MAPPING
#     else:  # api_football
#         return API_FOOTBALL_FIELD_MAPPING

# # Legacy mapping for backward compatibility
# FIELD_MAPPING = API_FOOTBALL_FIELD_MAPPING

# # =============================================================================
# # CONVERSION FUNCTIONS - Enhanced
# # =============================================================================

# def convert_birthdate(birth_input: Union[str, int, float, None]) -> Optional[date]:
#     """
#     Convert birth date from string or timestamp to date object.
#     """
#     if birth_input is None:
#         return None
    
#     try:
#         # Handle timestamp (SofaScore format)
#         if isinstance(birth_input, (int, float)):
#             # CÁCH TIẾP CẬN AN TOÀN CHO MỌI HỆ ĐIỀU HÀNH
#             # Epoch (mốc thời gian) là 1970-01-01 00:00:00 UTC
#             epoch = datetime(1970, 1, 1, tzinfo=pytz.UTC)
#             # Cộng/trừ số giây từ mốc thời gian
#             return (epoch + timedelta(seconds=birth_input)).date()
        
#         # Handle string (API-Football format)
#         if isinstance(birth_input, str):
#             # dateutil.parser đã đủ mạnh để xử lý hầu hết các định dạng
#             return parser.isoparse(birth_input).date()
            
#     except (ValueError, TypeError, OverflowError) as e:
#         # OverflowError có thể xảy ra với timedelta nếu timestamp quá lớn/nhỏ
#         logger.warning(f"Failed to convert birthdate '{birth_input}': {e}")
#         return None
    
#     return None

# def convert_accuracy(value: Union[str, int, float, None]) -> Optional[float]:
#     """Convert accuracy from % or number to float"""
#     if value is None:
#         return None
    
#     try:
#         if isinstance(value, str) and value.endswith('%'):
#             return float(value.rstrip('%')) / 100
#         return float(value)
#     except (TypeError, ValueError):
#         return None

# def convert_datetime(dt_input: Union[str, int, None]) -> Optional[datetime]:
#     """Convert datetime string or timestamp to UTC datetime object"""
#     if not dt_input:
#         return None
    
#     try:
#         # Handle timestamp (SofaScore format)
#         if isinstance(dt_input, (int, float)):
#             return datetime.fromtimestamp(dt_input, tz=pytz.UTC)
        
#         # Handle string (API-Football format)
#         if isinstance(dt_input, str):
#             dt = parser.isoparse(dt_input)
#             return dt.astimezone(pytz.UTC)
            
#     except (ValueError, TypeError, OSError) as e:
#         logger.warning(f"Failed to convert datetime '{dt_input}': {e}")
#         return None
    
#     return None

# def convert_timestamp_to_date(timestamp: Union[int, None]) -> Optional[date]:
#     """Convert timestamp to date (for SofaScore birth dates)"""
#     if not timestamp:
#         return None
    
#     try:
#         return datetime.fromtimestamp(timestamp, tz=pytz.UTC).date()
#     except (OSError, ValueError, TypeError):
#         return None

# def convert_possession_percent(value: Union[str, int, float, None]) -> Optional[float]:
#     """Convert possession percentage to float"""
#     if value is None:
#         return None
    
#     try:
#         if isinstance(value, str):
#             # Remove % sign if present
#             value = value.rstrip('%')
        
#         result = float(value)
#         # Ensure it's a valid percentage (0-100)
#         return max(0.0, min(100.0, result))
#     except (TypeError, ValueError):
#         return None

# # =============================================================================
# # SPECIAL CONVERSIONS 

# # API-Football special conversions
# API_FOOTBALL_SPECIAL_CONVERSIONS = {
#     "player.birth.date": convert_birthdate,
#     "passes.accuracy": convert_accuracy,
#     "statistics.pass_accuracy%": convert_accuracy,
#     "fixture.date": convert_datetime,
#     "statistics.ball_possession": convert_possession_percent
# }

# # SofaScore special conversions
# SOFASCORE_SPECIAL_CONVERSIONS = {
#     "startTimestamp": convert_datetime,
#     "homeTeam.foundationDateTimestamp": convert_birthdate,
#     "awayTeam.foundationDateTimestamp": convert_birthdate,
#     "player.dateOfBirthTimestamp": convert_birthdate,
# }

# def get_special_conversions(api_type: str = "sofascore") -> Dict[str, Callable]:
#     """Get special conversions for specified API"""
#     if api_type == "sofascore":
#         return SOFASCORE_SPECIAL_CONVERSIONS
#     else:  # api_football
#         return API_FOOTBALL_SPECIAL_CONVERSIONS

# # Legacy for backward compatibility
# SPECIAL_CONVERSIONS = API_FOOTBALL_SPECIAL_CONVERSIONS

# # =============================================================================
# # ENDPOINT CONFIGURATIONS

# # API-Football paginated endpoints
# API_FOOTBALL_PAGINATED_ENDPOINTS = [
#     "players", "fixtures", "teams", "transfers", 
#     "injuries", "trophies", "sidelined", "odds"
# ]

# # SofaScore endpoints that support pagination
# SOFASCORE_PAGINATED_ENDPOINTS = [
#     "events", "players", "seasons", "tournaments", "statistics"
# ]

# def get_paginated_endpoints(api_type: str = "sofascore") -> list:
#     """Get paginated endpoints for specified API"""
#     if api_type == "sofascore":
#         return SOFASCORE_PAGINATED_ENDPOINTS
#     else:  # api_football
#         return API_FOOTBALL_PAGINATED_ENDPOINTS

# # Legacy
# PAGINATED_ENDPOINTS = API_FOOTBALL_PAGINATED_ENDPOINTS

# # =============================================================================
# # DEFAULT VALUES AND CONSTANTS
# # =============================================================================

# # Timezone constants
# DEFAULT_TIMEZONE = "UTC"
# UK_TIMEZONE = "Europe/London"

# # Default values for player statistics
# DEFAULT_PLAYER_STATS = {
#     "minutes_played": 0,
#     "goals": 0,
#     "assists": 0,
#     "shots": 0,
#     "shots_on_target": 0,
#     "passes": 0,
#     "accurate_passes": 0,
#     "tackles": 0,
#     "duels_won": 0,
#     "fouls_committed": 0,
#     "yellow_cards": 0,
#     "red_cards": 0,
#     "possession_percent": 0.0,
#     "corner_kicks": 0,
#     "offsides": 0
# }

# # Default values for team statistics
# DEFAULT_TEAM_STATS = {
#     "matches_played": 0,
#     "wins": 0,
#     "draws": 0,
#     "losses": 0,
#     "goals_for": 0,
#     "goals_against": 0,
#     "goal_difference": 0,
#     "points": 0,
#     "clean_sheets": 0,
#     "failed_to_score": 0
# }

# # Legacy compatibility
# DEFAULT_VALUES = DEFAULT_PLAYER_STATS

# # =============================================================================
# # UTILITY FUNCTIONS
# # =============================================================================

# def get_default_value(field_name: str, api_type: str = "sofascore") -> Any:
#     """Get default value for a field"""
#     return DEFAULT_PLAYER_STATS.get(field_name, None)

# def build_sofascore_url(endpoint: str, **params) -> str:
#     """Build SofaScore API URL with parameters"""
#     try:
#         config = get_config()
#         base_url = str(config.sofascore.base_url).rstrip('/')
        
#         if params:
#             param_str = "&".join([f"{k}={v}" for k, v in params.items() if v is not None])
#             return f"{base_url}/{endpoint}?{param_str}"
#         else:
#             return f"{base_url}/{endpoint}"
#     except Exception:
#         return f"https://api.sofascore.com/api/v1/{endpoint}"

# def build_api_football_url(endpoint: str, **params) -> str:
#     """Build API-Football URL with parameters"""
#     try:
#         config = get_config()
#         base_url = str(config.api_football.base_url).rstrip('/')
        
#         if params:
#             param_str = "&".join([f"{k}={v}" for k, v in params.items() if v is not None])
#             return f"{base_url}/{endpoint}?{param_str}"
#         else:
#             return f"{base_url}/{endpoint}"
#     except Exception:
#         return f"https://v3.football.api-sports.io/{endpoint}"

# ai-engine/config/field_mappings.py

from datetime import datetime, date
import pytz
from dateutil import parser
import logging
from typing import Dict, Any, Optional, Union, Callable
from decimal import Decimal

# Import các hàm và Enum từ các file cấu hình khác đã được chuẩn hóa
from .core_constants import MatchStatus, PlayerPosition, MatchOutcome, PlayerStatus, MatchEventType, MatchPeriod
from .settings import get_config

# Khi xem log, chúng ta sẽ biết ngay thông báo này đến từ file `field_mappings.py`.
logger = logging.getLogger(__name__)

# SOFASCORE: ÁNH XẠ TÊN TRƯỜNG (FIELD NAME MAPPINGS)

# 1. Mapping cho các trường dữ liệu chính của trận đấu (từ gốc của JSON)
SOFASCORE_MATCH_FIELD_MAPPING: Dict[str, str] = {
    # Match Core & Metadata
    "id": "match_external_id",
    "startTimestamp": "match_timestamp",
    "status.description": "status_description",
    "roundInfo.round": "match_week",
    "winnerCode": "outcome_code",
    "attendance": "attendance",

    "homeScore.normaltime": "home_goals",
    "awayScore.normaltime": "away_goals",
    "homeScore.period1": "half_time_home_goals",
    "awayScore.period1": "half_time_away_goals",

    # League and Season
    "tournament.id": "league_external_id",
    "tournament.name": "league_name",
    "tournament.category.name": "league_country",
    "season.id": "season_external_id",
    "season.name": "season_name",
    "season.year": "season_year_str",

    # Home Team
    "homeTeam.id": "home_team_external_id",
    "homeTeam.name": "home_team_name",

    # Away Team
    "awayTeam.id": "away_team_external_id",
    "awayTeam.name": "away_team_name",

    # Match Venue
    "venue.id": "stadium_external_id",
    "venue.name": "stadium_name",
    "venue.city.name": "stadium_city",
    "venue.capacity": "stadium_capacity",
    "venue.venueCoordinates.latitude": "stadium_latitude",
    "venue.venueCoordinates.longitude": "stadium_longitude",

    "referee.id": "referee_external_id",
    "referee.name": "referee_name",
    "referee.country.name": "referee_country",
    "referee.games": "referee_total_games_officiated",
}

# 2. Mapping cho các trường chi tiết của một cầu thủ (trong mục lineups)
SOFASCORE_PLAYER_DETAILS_MAPPING: Dict[str, str] = {
    "player.id": "player_external_id",
    "player.name": "player_name",
    "player.position": "position_char",  # 'G', 'D', 'M', 'F'
    "player.dateOfBirthTimestamp": "dob_timestamp",
    "player.country.name": "nationality",
    "player.height": "height_cm",
    "shirtNumber": "shirt_number",
    "substitute": "is_substitute", # Dùng để suy ra is_starter
    "captain": "is_captain",
}

# 3. Mapping cho các chỉ số thống kê của cầu thủ (trong lineups -> player -> statistics)
SOFASCORE_PLAYER_STATS_MAPPING: Dict[str, str] = {
    "minutesPlayed": "minutes_played",
    "goals": "goals",
    "goalAssist": "assists",
    "totalScoringAttempt": "shots",
    "onTargetScoringAttempt": "shots_on_target",
    "totalPass": "passes",
    "accuratePass": "accurate_passes",
    "keyPass": "key_passes",
    "totalTackle": "tackles",
    "interceptionWon": "interceptions",
    "fouls": "fouls_committed",
    "wasFouled": "fouls_drawn",
    "yellowCard": "yellow_cards", 
    "redCard": "red_cards",     
    "saves": "saves",
}

# 4. Mapping cho các chỉ số thống kê của đội (trong mục statistics.statistics)
SOFASCORE_TEAM_STATS_MAPPING: Dict[str, str] = {
    "ballPossession": "possession_percentage",
    "totalShotsOnGoal": "total_shots",
    "shotsOnGoal": "shots_on_target",
    "shotsOffGoal": "shots_off_target",
    "blockedScoringAttempt": "blocked_shots",
    "fouls": "fouls_committed",
    "cornerKicks": "corners",
    "offsides": "offsides",
    "goalkeeperSaves": "saves",
    "yellowCards": "yellow_cards", 
    "redCards": "red_cards",    
}

# CÁC HÀM CHUYỂN ĐỔI (CONVERSION FUNCTIONS)

def convert_timestamp_to_utc_datetime(timestamp: Optional[Union[int, float]]) -> Optional[datetime]:
    """
    Chuyển đổi Unix timestamp (số giây từ 1/1/1970) thành đối tượng datetime có nhận biết múi giờ UTC.
    - Input: Một số nguyên hoặc số thực (ví dụ: 1672531200).
    - Output: Một đối tượng datetime (ví dụ: datetime(2023, 1, 1, 0, 0, tzinfo=<UTC>)) hoặc None nếu lỗi.
    - Tại sao UTC?: Chuẩn hóa tất cả thời gian về một múi giờ duy nhất (UTC) là cực kỳ quan trọng để tránh nhầm lẫn và sai sót khi làm việc với dữ liệu từ nhiều nguồn hoặc trên các server khác nhau.
    """
    if timestamp is None: return None
    try:
        return datetime.fromtimestamp(timestamp, tz=pytz.UTC)
    except (OSError, TypeError, ValueError) as e:
        logger.warning(f"Failed to convert timestamp '{timestamp}' to datetime: {e}")
        return None

def convert_timestamp_to_date(timestamp: Optional[Union[int, float]]) -> Optional[date]:
    """
    Chuyển đổi Unix timestamp thành đối tượng date (chỉ lấy ngày, không lấy giờ).
    - Logic: Tái sử dụng hàm trên để lấy đối tượng datetime, sau đó chỉ trả về phần ngày (.date()).
    - Ứng dụng: Hữu ích cho việc lưu ngày sinh, không cần quan tâm đến giờ sinh.
    """
    dt = convert_timestamp_to_utc_datetime(timestamp)
    return dt.date() if dt else None

def convert_possession_to_decimal(value: Optional[str]) -> Optional[Decimal]:
    """
    Chuyển đổi chuỗi phần trăm (ví dụ: '60%') thành số Decimal (ví dụ: 60.00).
    - Input: Một chuỗi như "55%".
    - Output: Một đối tượng Decimal như Decimal('55').
    - Tại sao Decimal?: Sử dụng Decimal thay vì float để tránh các lỗi làm tròn không mong muốn. Điều này quan trọng khi thực hiện các phép tính tài chính hoặc thống kê cần độ chính xác cao.
    """
    if value is None: return None
    try:
        # Loại bỏ ký tự '%' và chuyển thành Decimal để giữ độ chính xác
        return Decimal(str(value).rstrip('%'))
    except (ValueError, TypeError):
        return None

# ÁNH XẠ CHUYỂN ĐỔI ĐẶC BIỆT (SPECIAL CONVERSIONS MAPPING)
# Liên kết TÊN TRƯỜNG NỘI BỘ (đã được dịch từ mapping ở trên) với HÀM CHUYỂN ĐỔI tương ứng.

SOFASCORE_SPECIAL_CONVERSIONS: Dict[str, Callable] = {
    # Tên trường nội bộ         # Hàm sẽ được gọi để xử lý giá trị của trường đó
    "match_timestamp":           convert_timestamp_to_utc_datetime,
    "dob_timestamp":             convert_timestamp_to_date,
    "possession_percentage":     convert_possession_to_decimal,
}