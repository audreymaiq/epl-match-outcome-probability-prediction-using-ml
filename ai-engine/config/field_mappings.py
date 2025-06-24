# ai-engine/config/field_mappings.py

from datetime import datetime, date
import requests
import pytz
from dateutil import parser
import logging
from .core_constants import (
    API_POSITION_MAPPING,
    API_STATUS_MAPPING,
    API_OUTCOME_MAPPING,
    API_PLAYER_AVAILABILITY_MAPPING,  # FIXED: Import đúng tên
    PlayerAvailabilityStatus
)
from .settings import config

# Hàm helper cho mapping an toàn
logger = logging.getLogger(__name__)

def safe_mapping(mapping, default=None, log_missing=False):
    def mapper(value):
        if value not in mapping and log_missing:
            logger.warning(f"Missing mapping for '{value}'")
        return mapping.get(value, default)
    return mapper


# Mapping vị trí cầu thủ từ API sang schema
position_mapper = safe_mapping(API_POSITION_MAPPING, default=None)

# Mapping trạng thái trận đấu
status_mapper = safe_mapping(API_STATUS_MAPPING, default=None)

# Mapping kết quả trận đấu
outcome_mapper = safe_mapping(API_OUTCOME_MAPPING, default=None)

# Mapping loại sự kiện (MatchEvents.event_type)
EVENT_TYPE_MAPPING = {
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
event_type_mapper = safe_mapping(EVENT_TYPE_MAPPING, default="unknown")

# Mapping giai đoạn trận đấu (MatchEvents.period)
PERIOD_MAPPING = {
    "1H": "first_half",
    "2H": "second_half",
    "HT": "halftime",
    "ET": "extra_time",
    "P": "penalty_shootout",
    "BT": "break_time"
}
period_mapper = safe_mapping(PERIOD_MAPPING, default=None)

# FIXED: Sử dụng mapping từ core_constants.py thay vì tự định nghĩa
player_status_mapper = safe_mapping(API_PLAYER_AVAILABILITY_MAPPING, default=PlayerAvailabilityStatus.UNKNOWN)

# Mapping vị trí địa lý (TeamSeasonLocationStats.location)
LOCATION_MAPPING = {
    "home": "home",
    "away": "away",
    "total": "overall"
}
location_mapper = safe_mapping(LOCATION_MAPPING, default="overall")

# Mapping cho thống kê thẻ (RefereeStats)
CARD_MAPPING = {
    "yellow": "yellow_cards",
    "red": "red_cards"
}
card_mapper = safe_mapping(CARD_MAPPING, default=None)

# Mapping cho dữ liệu bookmaker (BettingOdds)
def load_bookmaker_mapping():
    """
    Gọi API-Football /odds/bookmakers để lấy dictionary id->name.
    """
    url = f"{config.api.base_url}/odds/bookmakers"
    headers = {
        "x-rapidapi-host": config.api.base_url.split('://')[-1],
        "x-rapidapi-key": config.api.get_random_key()
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("response", [])
        return {int(item["id"]): item["name"] for item in data}
    except Exception as e:
        logger.error(f"Failed to load bookmaker mapping: {e}")
        return {}

# FIXED: Thêm lazy loading để tránh lỗi khi config chưa sẵn sàng
_bookmaker_mapping = None

def get_bookmaker_mapping():
    global _bookmaker_mapping
    if _bookmaker_mapping is None:
        _bookmaker_mapping = load_bookmaker_mapping()
    return _bookmaker_mapping

def bookmaker_mapper(bookmaker_id):
    mapping = get_bookmaker_mapping()
    return mapping.get(bookmaker_id, "Unknown")

# API field to database column mapping
FIELD_MAPPING = {
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

# Hàm chuyển đổi đặc biệt
def convert_birthdate(birth_str):
    """Chuyển đổi ngày sinh từ string sang date object"""
    if not birth_str:
        return None
    try:
        return parser.isoparse(birth_str).date()
    except ValueError:
        return None

def convert_accuracy(value):
    """Chuyển đổi độ chính xác từ % hoặc số sang float"""
    if value is None:
        return None
    if isinstance(value, str) and value.endswith('%'):
        try:
            return float(value.rstrip('%')) / 100
        except ValueError:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def convert_datetime(dt_str):
    """Chuyển đổi datetime string sang UTC datetime object"""
    if not dt_str:
        return None
    try:
        dt = parser.isoparse(dt_str)
        return dt.astimezone(pytz.UTC)
    except (ValueError, TypeError):
        return None

# Danh sách các trường cần chuyển đổi đặc biệt
SPECIAL_CONVERSIONS = {
    "player.birth.date": convert_birthdate,
    "passes.accuracy": convert_accuracy,
    "statistics.pass_accuracy%": convert_accuracy,
    "fixture.date": convert_datetime
}

# Các endpoint cần phân trang
PAGINATED_ENDPOINTS = [
    "players",
    "fixtures", 
    "teams",
    "transfers",
    "injuries",
    "trophies",
    "sidelined",
    "odds"
]

# Timezone mặc định cho dữ liệu
DEFAULT_TIMEZONE = "UTC"

# Các giá trị mặc định cho các trường thống kê cầu thủ
DEFAULT_VALUES = {
    "minutes_played": 0,
    "goals": 0,
    "assists": 0,
    "shots_total": 0,
    "shots_on": 0,
    "passes_total": 0,
    "passes_accuracy": 0.0,
    "tackles": 0,
    "duels_won": 0,
    "fouls_committed": 0,
    "yellow_cards": 0,
    "red_cards": 0
}