# ai-engine/config/field_mappings.py

from datetime import datetime
from .core_constants import API_POSITION_MAPPING, API_STATUS_MAPPING, API_OUTCOME_MAPPING

# Mapping vị trí cầu thủ từ API sang schema
POSITION_MAPPING = {key: value.value for key, value in API_POSITION_MAPPING.items()}

# Mapping trạng thái trận đấu
STATUS_MAPPING = {api_code: status.value for api_code, status in API_STATUS_MAPPING.items()}

# Mapping kết quả trận đấu
OUTCOME_MAPPING = {key: value.value for key, value in API_OUTCOME_MAPPING.items()}

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
}

# Mapping giai đoạn trận đấu (MatchEvents.period)
PERIOD_MAPPING = {
    "1H": "1H",
    "2H": "2H",
    "ET": "ET1",
    "P": "PEN",
    "BT": "HT"
}

# Mapping tình trạng cầu thủ (SquadAvailability.status)
PLAYER_STATUS_MAPPING = {
    "Missing Fixture": "Injured",
    "Questionable": "Doubtful",
    "Suspended": "Suspended",
    "Not Available": "Away on Intl Duty"
}

# Mapping vị trí địa lý (TeamSeasonLocationStats.location)
LOCATION_MAPPING = {
    "home": "Home",
    "away": "Away",
    "total": "Overall"
}

# Mapping cho thống kê thẻ (RefereeStats)
CARD_MAPPING = {
    "yellow": "avg_yellow_cards_per_match",
    "red": "avg_red_cards_per_match"
}

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

# API field to database column mapping
FIELD_MAPPING = {
    "league.id": "id",
    "league.name": "name",
    "league.country": "country",
    "league.logo": "logo_url",
    "team.id": "id",
    "team.name": "name",
    "team.code": "short_name",
    "team.founded": "established_year",
    "venue.id": "id",
    "venue.name": "name",
    "venue.city": "city",
    "venue.capacity": "capacity",
    "player.id": "id",
    "player.name": "name",
    "player.age": "date_of_birth",
    "player.height": "height",
    "player.nationality": "nationality",
    "fixture.id": "id",
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
    "saves": "saves"
}

# Danh sách các trường cần chuyển đổi đặc biệt
SPECIAL_CONVERSIONS = {
    "player.age": lambda age: datetime.now().year - int(age),
    "passes.accuracy": lambda pct: int(pct.replace('%', '')) / 100
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

# Giá trị mặc định cho các trường
DEFAULT_VALUES = {
    "height": 180,
    "capacity": 10000,
    "minutes_played": 90
}