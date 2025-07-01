# ai-engine/config/business_constants.py

from enum import Enum
from typing import List, Tuple, FrozenSet, Dict, Any, Optional, Union
from functools import lru_cache
from datetime import datetime, timedelta
import pytz
import re

from config.settings import get_config
from .core_constants import PlayerPosition, MatchStatus, MatchOutcome

import logging
logger = logging.getLogger(__name__)

# ======================== CONFIGURATION LOADING ========================
@lru_cache(maxsize=1)
def _get_config():
    """Cached lazy load configuration to avoid circular imports"""
    return get_config()

# ======================== LEAGUE AND COMPETITION TYPES ========================
class LeagueType(Enum):
    """Phân loại các giải đấu"""
    PREMIER_LEAGUE = "EPL"
    CHAMPIONSHIP = "CHAMPIONSHIP"
    LEAGUE_ONE = "LEAGUE_ONE"
    LEAGUE_TWO = "LEAGUE_TWO"

class MatchImportance(Enum):
    """Mức độ quan trọng của trận đấu"""
    HIGH = "HIGH"          # Derby, Top 6 clash, Title decider
    MEDIUM = "MEDIUM"      # Mid-table vs Top 6, Relegation battle
    LOW = "LOW"           # Mid-table clash
    UNKNOWN = "UNKNOWN"

class TeamCategory(Enum):
    """Phân loại đội bóng theo thành tích"""
    BIG_SIX = "BIG_SIX"           # Top 6 traditional teams
    ESTABLISHED = "ESTABLISHED"   # Regularly in PL for 5+ years
    PROMOTED = "PROMOTED"         # Recently promoted teams
    RELEGATION_BATTLE = "RELEGATION_BATTLE"  # Fighting relegation
    UNKNOWN = "UNKNOWN"

class TeamPerformanceCategory(Enum):
    """Categories for team performance analysis"""
    EXCELLENT = "excellent"
    GOOD = "good" 
    AVERAGE = "average"
    POOR = "poor"
    VERY_POOR = "very_poor"

# ======================== MATCH STATUSES ========================
MatchStatusCategory = MatchStatus

# ======================== PLAYER POSITIONS ========================
# POSITION_MAPPING = API_POSITION_MAPPING

# ======================== ENTITY TYPES ========================
VALID_ENTITY_TYPES: FrozenSet[str] = frozenset({
    'team', 'player', 'match', 'stadium', 'league', 'referee'
})

# Constants that can be computed once
SEASON_FORMAT: str = "{start}/{end}"

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

# ======================== BUSINESS RULES ========================
class BusinessRules:
    """Các quy tắc nghiệp vụ cho Premier League"""
    
    # Premier League Business Constants
    SEASON_START_MONTH = 8  # August
    SEASON_END_MONTH = 5    # May
    TOTAL_TEAMS = 20
    MATCHES_PER_TEAM_PER_SEASON = 38
    TOTAL_MATCHES_PER_SEASON = 380
    
    # Points system
    POINTS_WIN = 3
    POINTS_DRAW = 1
    POINTS_LOSS = 0
    
    # Table positions
    CHAMPIONS_LEAGUE_POSITIONS = [1, 2, 3, 4]
    EUROPA_LEAGUE_POSITIONS = [5]
    CONFERENCE_LEAGUE_POSITIONS = [6]  # Winner of domestic cups
    RELEGATION_POSITIONS = [18, 19, 20]
    
    # Historical Big Six teams (traditional top 6)
    BIG_SIX_TEAMS = [
        "Arsenal", "Chelsea", "Liverpool", 
        "Manchester City", "Manchester United", "Tottenham"
    ]
    
    # Team name variations and normalization
    TEAM_NAME_MAPPING = {
        # Manchester teams
        "Manchester City": ["Man City", "Manchester City FC", "Man City FC"],
        "Manchester United": ["Man United", "Manchester United FC", "Man Utd", "Man United FC"],
        
        # London teams
        "Arsenal": ["Arsenal FC", "The Gunners"],
        "Chelsea": ["Chelsea FC", "The Blues"],
        "Tottenham": ["Tottenham Hotspur", "Spurs", "Tottenham Hotspur FC"],
        "Crystal Palace": ["Crystal Palace FC", "Palace"],
        "Fulham": ["Fulham FC"],
        "West Ham": ["West Ham United", "West Ham United FC", "The Hammers"],
        "Brentford": ["Brentford FC"],
        
        # Liverpool teams
        "Liverpool": ["Liverpool FC", "The Reds"],
        "Everton": ["Everton FC", "The Toffees"],
        
        # Other notable teams
        "Newcastle": ["Newcastle United", "Newcastle United FC", "The Magpies"],
        "Aston Villa": ["Aston Villa FC", "Villa"],
        "Brighton": ["Brighton & Hove Albion", "Brighton & Hove Albion FC", "The Seagulls"],
        "Leicester": ["Leicester City", "Leicester City FC", "The Foxes"],
        "Leeds": ["Leeds United", "Leeds United FC"],
        "Sheffield United": ["Sheffield United FC", "The Blades"],
        "Wolverhampton": ["Wolves", "Wolverhampton Wanderers FC", "Wolves FC"]
    }
    
    # Derby matches (high importance)
    DERBY_MATCHES = {
        "North London Derby": ["Arsenal", "Tottenham"],
        "Manchester Derby": ["Manchester City", "Manchester United"],
        "Merseyside Derby": ["Liverpool", "Everton"],
        "London Derby": [
            "Arsenal", "Chelsea", "Tottenham", "Crystal Palace", 
            "Fulham", "West Ham", "Brentford"
        ]
    }
    
    # Match scheduling patterns
    TYPICAL_KICKOFF_TIMES = {
        "saturday_early": "12:30",
        "saturday_main": "15:00", 
        "saturday_late": "17:30",
        "sunday_early": "14:00",
        "sunday_late": "16:30",
        "monday_night": "20:00",
        "midweek": "19:45"
    }
    
    # Season phases
    SEASON_PHASES = {
        "early": (8, 10),      # August - October
        "autumn": (11, 12),    # November - December
        "winter": (1, 2),      # January - February
        "spring": (3, 5)       # March - May
    }

# ======================== DATA QUALITY RULES ========================
class DataQualityRules:
    """Quy tắc về chất lượng dữ liệu"""
    
    # Match data validation
    MIN_MATCH_DURATION = 90  # minutes
    MAX_MATCH_DURATION = 120  # with extra time
    
    MAX_GOALS_PER_TEAM = 10  # Reasonable upper limit
    MAX_CARDS_PER_TEAM = 5   # Red cards would reduce players
    
    # Player statistics validation
    MIN_PLAYER_MINUTES = 0
    MAX_PLAYER_MINUTES = 120
    
    MAX_GOALS_PER_PLAYER_PER_MATCH = 5  # Theoretical maximum
    MAX_ASSISTS_PER_PLAYER_PER_MATCH = 3
    
    # Team statistics validation
    MIN_POSSESSION_PERCENTAGE = 0
    MAX_POSSESSION_PERCENTAGE = 100
    
    MIN_SHOTS = 0
    MAX_SHOTS = 50  # Very attacking game
    
    MAX_FOULS_PER_TEAM = 30
    MAX_CORNERS_PER_TEAM = 20

# ======================== SCRAPING BUSINESS RULES ========================
class ScrapingBusinessRules:
    """Quy tắc nghiệp vụ cho việc scraping dữ liệu"""
    
    # Data freshness requirements
    MATCH_DATA_STALENESS_HOURS = 6  # Refresh match data if older than 6 hours
    TEAM_STATS_STALENESS_DAYS = 1   # Refresh team stats daily
    PLAYER_STATS_STALENESS_DAYS = 7 # Refresh player stats weekly
    
    # Scraping priorities
    PRIORITY_MATCHES = [
        "IN_PROGRESS",    # Live matches
        "SCHEDULED",      # Upcoming matches
        "FINISHED"        # Recently finished
    ]
    
    # Retry logic for failed scraping
    MAX_SCRAPING_RETRIES = 3
    SCRAPING_RETRY_DELAY_SECONDS = [2, 5, 10]  # Exponential backoff
    
    # Data completeness requirements
    REQUIRED_MATCH_FIELDS = [
        "home_team", "away_team", "kickoff_time", 
        "status", "home_score", "away_score"
    ]
    
    OPTIONAL_MATCH_FIELDS = [
        "referee", "venue", "attendance", "weather"
    ]

# ======================== ANALYTICS CONSTANTS ========================
class AnalyticsConstants:
    """Constants cho analytics và machine learning"""
    
    # Feature engineering
    FORM_MATCHES_COUNT = 5  # Last 5 matches for form calculation
    HEAD_TO_HEAD_MATCHES_COUNT = 10  # H2H history depth
    
    # Performance metrics
    EXPECTED_GOALS_THRESHOLD = 0.1  # Minimum xG to be considered a chance
    BIG_CHANCE_XG_THRESHOLD = 0.35  # xG threshold for "big chances"
    
    # Team strength indicators
    BIG_WIN_GOAL_DIFFERENCE = 3  # 3+ goal margin
    COMFORTABLE_WIN_GOAL_DIFFERENCE = 2
    
    # Home advantage
    HISTORICAL_HOME_WIN_PERCENTAGE = 46  # Historical Premier League average
    HISTORICAL_AWAY_WIN_PERCENTAGE = 29
    HISTORICAL_DRAW_PERCENTAGE = 25

# ======================== SEASON BUSINESS LOGIC ========================
class SeasonBusinessLogic:
    """Logic nghiệp vụ liên quan đến mùa giải"""
    
    @staticmethod
    def get_season_from_year(year: int) -> str:
        """Convert năm thành tên mùa giải (ví dụ: 2023 -> "2023/24")"""
        return f"{year}/{str(year + 1)[-2:]}"
    
    @staticmethod
    def extract_year_from_season(season_name: Optional[str]) -> Optional[int]:
        """
        Extract năm bắt đầu từ tên mùa giải (ví dụ: "2023/24" -> 2023).
        Xử lý nhiều định dạng và trả về None nếu không hợp lệ.
        """
        if not season_name:
            return None
        
        # Biểu thức chính quy để tìm các định dạng năm `năm/năm` hoặc `năm-năm`
        # Ưu tiên tìm định dạng 4 số trước.
        # (\d{4})[/-]\d+  -> Tìm "2023" trong "2023/24" hoặc "2023-2024"
        # (\d{2})[/-]\d+   -> Tìm "23" trong "23/24" hoặc "23-24"
        match = re.search(r'(\d{4})[/-]\d+|(\d{2})[/-]\d+', season_name)

        if match:
            year_str = match.group(1) or match.group(2)

            try:
                # Nếu là định dạng 2 số (ví dụ "23"), chuyển thành 4 số ("2023")
                if len(year_str) == 2:
                    return int(f"20{year_str}")
                # Nếu đã là 4 số
                else:
                    return int(year_str)
            except ValueError:
                # Trường hợp rất hiếm, nhưng vẫn phòng thủ
                logger.warning(f"Regex matched but failed to convert to int: '{year_str}' from '{season_name}'")
                return None

        logger.warning(f"Could not parse a valid season year pattern from '{season_name}'")
        return None
    
    @staticmethod
    def is_season_complete(season: str, timezone: str = "Europe/London") -> bool:
        """Kiểm tra mùa giải đã hoàn thành chưa"""
        try:
            season_year = SeasonBusinessLogic.extract_year_from_season(season)
            season_end_year = season_year + 1
            
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            
            # Mùa giải kết thúc vào cuối tháng 5
            season_end = tz.localize(datetime(season_end_year, 5, 31))
            
            return now > season_end
        except Exception:
            return False
    
    @staticmethod
    def get_current_season(timezone: str = "Europe/London") -> str:
        """Lấy mùa giải hiện tại"""
        try:
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            
            # Mùa giải mới bắt đầu từ tháng 8
            if now.month >= BusinessRules.SEASON_START_MONTH:
                season_start_year = now.year
            else:
                season_start_year = now.year - 1
                
            return SeasonBusinessLogic.get_season_from_year(season_start_year)
        except Exception:
            # Fallback
            current_year = datetime.now().year
            if datetime.now().month >= 8:
                return f"{current_year}/{str(current_year + 1)[-2:]}"
            else:
                return f"{current_year - 1}/{str(current_year)[-2:]}"

# ======================== MATCH BUSINESS LOGIC ========================
class MatchBusinessLogic:
    """Logic nghiệp vụ liên quan đến trận đấu"""
    
    @staticmethod
    def determine_match_importance(home_team: str, away_team: str) -> MatchImportance:
        """Xác định mức độ quan trọng của trận đấu"""
        
        # Check if it's a derby
        for derby_name, teams in BusinessRules.DERBY_MATCHES.items():
            if home_team in teams and away_team in teams:
                return MatchImportance.HIGH
        
        # Check if both teams are Big Six
        both_big_six = (
            home_team in BusinessRules.BIG_SIX_TEAMS and 
            away_team in BusinessRules.BIG_SIX_TEAMS
        )
        if both_big_six:
            return MatchImportance.HIGH
        
        # One team is Big Six
        one_big_six = (
            home_team in BusinessRules.BIG_SIX_TEAMS or 
            away_team in BusinessRules.BIG_SIX_TEAMS
        )
        if one_big_six:
            return MatchImportance.MEDIUM
        
        return MatchImportance.LOW
    
    @staticmethod
    def normalize_team_name(team_name: str) -> str:
        """Chuẩn hóa tên đội bóng"""
        if not team_name:
            return ""
        
        team_name = team_name.strip()
        
        # Check exact matches first
        for standard_name, variations in BusinessRules.TEAM_NAME_MAPPING.items():
            if team_name == standard_name:
                return standard_name
            if team_name in variations:
                return standard_name
        
        # If no match found, return original (title case)
        return team_name.title()
    
    @staticmethod
    def calculate_points(goals_for: int, goals_against: int) -> int:
        """Tính điểm từ kết quả trận đấu"""
        if goals_for > goals_against:
            return BusinessRules.POINTS_WIN
        elif goals_for == goals_against:
            return BusinessRules.POINTS_DRAW
        else:
            return BusinessRules.POINTS_LOSS
    
    @staticmethod
    def is_big_win(goals_for: int, goals_against: int) -> bool:
        """Kiểm tra có phải thắng đậm không"""
        return (goals_for - goals_against) >= AnalyticsConstants.BIG_WIN_GOAL_DIFFERENCE

# ======================== VALIDATION RULES ========================
class ValidationRules:
    """Các quy tắc validation dữ liệu"""
    
    @staticmethod
    def validate_match_score(home_score: Optional[int], away_score: Optional[int]) -> bool:
        """Validate điểm số trận đấu"""
        if home_score is None or away_score is None:
            return False
        
        return (
            0 <= home_score <= DataQualityRules.MAX_GOALS_PER_TEAM and
            0 <= away_score <= DataQualityRules.MAX_GOALS_PER_TEAM
        )
    
    @staticmethod
    def validate_possession(home_possession: Optional[float], away_possession: Optional[float]) -> bool:
        """Validate possession percentage"""
        if home_possession is None or away_possession is None:
            return False
        
        # Should add up to approximately 100%
        total = home_possession + away_possession
        return 99 <= total <= 101  # Allow small rounding errors
    
    @staticmethod
    def validate_team_name(team_name: str) -> bool:
        """Validate tên đội bóng"""
        if not team_name or not isinstance(team_name, str):
            return False
        
        # Should not be empty after stripping
        return len(team_name.strip()) > 0

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

# ======================== MODULE EXPORTS ========================
__all__ = [
    # Enums
    'LeagueType', 'MatchImportance', 'TeamCategory', 'TeamPerformanceCategory',
    'MLOutcomeLabels', 'MatchStatusCategory',
    
    # Classes
    'BusinessRules', 'DataQualityRules', 'ScrapingBusinessRules',
    'AnalyticsConstants', 'SeasonBusinessLogic', 'MatchBusinessLogic',
    'ValidationRules',
    
    # Constants
    # 'MATCH_STATUS_MAPPING', 'POSITION_MAPPING', 'OUTCOME_MAPPING','SEASONS_TO_FETCH',
    'VALID_ENTITY_TYPES', 'SEASON_FORMAT', 
    'PLAYER_POSITION_LABELS', 'MATCH_STATUS_LABELS',
    'POSITION_LABELS_REVERSE', 'STATUS_LABELS_REVERSE',
    'LABEL_MAPPERS', 'PERFORMANCE_THRESHOLDS',
    
    # Match constants
    'MINUTES_IN_MATCH', 'EXTRA_TIME_MINUTES', 'PENALTY_SHOOTOUT_ROUNDS',
    'HALFTIME_BREAK_MINUTES', 'FIRST_HALF_MINUTES', 'SECOND_HALF_MINUTES',
    'FIRST_EXTRA_TIME_MINUTES', 'SECOND_EXTRA_TIME_MINUTES',
    
    # Thresholds
    'POSSESSION_THRESHOLD', 'SHOTS_ON_TARGET_THRESHOLD', 'CORNERS_THRESHOLD',
    'CARDS_THRESHOLD', 'FOULS_THRESHOLD', 'PASS_ACCURACY_THRESHOLD',
    'HIGH_SCORING_THRESHOLD', 'LOW_SCORING_THRESHOLD',
    
    # League constants
    'PREMIER_LEAGUE_TEAMS', 'PREMIER_LEAGUE_MATCHES_PER_SEASON',
    'PREMIER_LEAGUE_ROUNDS', 'WIN_POINTS', 'DRAW_POINTS', 'LOSS_POINTS',
    
    # Functions
    # 'get_current_season', 'get_last_completed_season', 'get_seasons_to_fetch',
    # 'get_default_seasons_to_fetch', 
    'categorize_team_performance',
    'encode_player_position', 'decode_player_position',
    'encode_match_status', 'decode_match_status',
    'format_season', 'parse_season_string', 'is_valid_season',
    'validate_constants'
]

# Run validation
if __name__ == "__main__":
    try:
        validate_constants()
        print("Business constants validation passed.")
    except Exception as e:
        print(f"Business constants validation failed: {e}")

