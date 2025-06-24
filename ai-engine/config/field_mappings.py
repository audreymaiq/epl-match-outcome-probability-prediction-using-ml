# ai-engine/config/field_mappings.py

from datetime import datetime, date
import pytz
from dateutil import parser
from .core_constants import API_POSITION_MAPPING, API_STATUS_MAPPING, API_OUTCOME_MAPPING

# Hàm helper cho mapping an toàn
def safe_mapping(mapping, default="UNKNOWN"):
    def mapper(value):
        return mapping.get(value, default)
    return mapper

# Mapping vị trí cầu thủ từ API sang schema
POSITION_MAPPING = {key: value.value for key, value in API_POSITION_MAPPING.items()}
position_mapper = safe_mapping(POSITION_MAPPING, "UNKNOWN")

# Mapping trạng thái trận đấu
STATUS_MAPPING = {api_code: status.value for api_code, status in API_STATUS_MAPPING.items()}
status_mapper = safe_mapping(STATUS_MAPPING, "UNKNOWN")

# Mapping kết quả trận đấu
OUTCOME_MAPPING = {key: value.value for key, value in API_OUTCOME_MAPPING.items()}
outcome_mapper = safe_mapping(OUTCOME_MAPPING, "UNKNOWN")

# Mapping loại sự kiện (MatchEvents.event_type)
EVENT_TYPE_MAPPING = {
    "Goal": "goal",
    "Normal Goal": "goal",
    "Own Goal": "own_goal",
    "Penalty": "penalty_goal",
    "Missed Penalty": "missed_penalty",
    "Yellow Card": "yellow_card",
    "Red Card": "red_card",
    "Second Yellow card": "second_yellow",
    "Substitution": "substitution",
    "Goal cancelled": "goal_cancelled",
    "Penalty confirmed": "penalty_confirmed",
    "Foul": "foul",
    "Corner": "corner",
    "Offside": "offside",
    "Hand ball": "handball",
    "Free Kick": "free_kick",
    "Injury": "injury",
    "Injury Time": "injury_time",
    "VAR Decision": "var_decision",
    "Goal Disallowed": "goal_disallowed"
}
event_type_mapper = safe_mapping(EVENT_TYPE_MAPPING, "unknown")

# Mapping giai đoạn trận đấu (MatchEvents.period)
PERIOD_MAPPING = {
    "1H": "1H",
    "2H": "2H",
    "1H+": "1H_extra",
    "2H+": "2H_extra",
    "ET": "ET1",
    "ET2": "ET2",
    "P": "PEN",
    "BT": "HT",
    "BT_ET": "BT_ET"
}
period_mapper = safe_mapping(PERIOD_MAPPING, "UNKNOWN")

# Mapping tình trạng cầu thủ (SquadAvailability.status)
PLAYER_STATUS_MAPPING = {
    "Missing Fixture": "Injured",
    "Questionable": "Doubtful",
    "Suspended": "Suspended",
    "Not Available": "Away on Intl Duty",
    "Available": "Available"  # Bổ sung giá trị còn thiếu
}
player_status_mapper = safe_mapping(PLAYER_STATUS_MAPPING, "Available")

# Mapping vị trí địa lý (TeamSeasonLocationStats.location)
LOCATION_MAPPING = {
    "home": "Home",
    "away": "Away",
    "total": "Overall"
}
location_mapper = safe_mapping(LOCATION_MAPPING, "Overall")

# Mapping cho thống kê thẻ (RefereeStats)
CARD_MAPPING = {
    "yellow": "avg_yellow_cards_per_match",
    "red": "avg_red_cards_per_match"
}
card_mapper = safe_mapping(CARD_MAPPING, "unknown")

# Mapping cho dữ liệu bookmaker (BettingOdds)
BOOKMAKER_MAPPING = {
    1: "Bet365",
    2: "William Hill",
    3: "Ladbrokes",
    4: "Pinnacle",
    5: "Unibet",
    6: "Betfair",
    8: "888sport",
    9: "10Bet",
    10: "Betway",
    11: "Marathon Bet",
    12: "1xBet",
    13: "Bwin",
    14: "Interwetten",
    15: "Tipico"
}
bookmaker_mapper = safe_mapping(BOOKMAKER_MAPPING, "Unknown")

# API field to database column mapping - SỬA XUNG ĐỘT TÊN
FIELD_MAPPING = {
    "league.id": "league_id",
    "league.name": "name",
    "league.country": "country",
    "league.logo": "logo_url",
    "team.id": "team_id",
    "team.name": "name",
    "team.code": "short_name",
    "team.founded": "established_year",
    "venue.id": "venue_id",
    "venue.name": "name",
    "venue.city": "city",
    "venue.capacity": "capacity",
    "player.id": "player_id",
    "player.name": "name",
    "player.birth.date": "date_of_birth",  # Sử dụng trường ngày sinh thay vì tuổi
    "player.height": "height",
    "player.nationality": "nationality",
    "fixture.id": "fixture_id",
    "fixture.date": "match_datetime",
    "fixture.referee": "referee_id",
    "teams.home.id": "home_team_id",
    "teams.away.id": "away_team_id",
    "goals.home": "home_goals",
    "goals.away": "away_goals",
    "score.halftime.home": "half_time_home_goals",
    "score.halftime.away": "half_time_away_goals",
    "games.minutes": "minutes_played",
    "goals.total": "goals",
    "goals.assists": "assists",
    "shots.total": "shots",
    "shots.on": "shots_on_target",
    "passes.total": "passes",
    "passes.accuracy": "accurate_passes",
    "tackles.total": "tackles",
    "duels.won": "interceptions",
    "fouls.committed": "fouls_committed",
    "cards.yellow": "yellow_cards",
    "cards.red": "red_cards",
    "saves": "saves",
    
    # Bổ sung các trường mới từ API document
    "statistics.ball_possession": "possession_percentage",
    "statistics.corner_kicks": "corners",
    "statistics.offsides": "offsides",
    "statistics.total_passes": "total_passes",
    "statistics.passes_accurate": "accurate_passes",
    "statistics.pass_accuracy%": "pass_accuracy_percent"
}

# Hàm chuyển đổi đặc biệt - SỬA LỖI NGHIÊM TRỌNG
def convert_birthdate(birth_str):
    """Chuyển đổi ngày sinh từ string sang date object"""
    if not birth_str:
        return None
    try:
        return parser.parse(birth_str).date()
    except:
        return None

def convert_accuracy(value):
    """Xử lý giá trị phần trăm an toàn"""
    if value is None:
        return 0.0
    if isinstance(value, str):
        clean_value = value.replace('%', '').strip()
        return float(clean_value) / 100 if clean_value else 0.0
    return float(value)

def convert_datetime(dt_str):
    """Chuyển đổi datetime với timezone"""
    if not dt_str:
        return None
    try:
        dt = parser.isoparse(dt_str)
        return dt.astimezone(pytz.UTC)  # Chuyển về UTC
    except:
        return None

# Danh sách các trường cần chuyển đổi đặc biệt - ĐÃ SỬA
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
    "injuries"
]

# Timezone mặc định cho dữ liệu
DEFAULT_TIMEZONE = "UTC"

# Giá trị mặc định cho các trường - ĐÃ SỬA
DEFAULT_VALUES = {
    "height": None,
    "capacity": None,
    "minutes_played": None,
    "date_of_birth": None,
    "accurate_passes": 0.0
}