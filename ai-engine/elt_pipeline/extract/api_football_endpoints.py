# ai-engine\elt_pipeline\extract\api_endpoints.py

import os
from urllib.parse import urlencode
from enum import Enum

class APIFootballEndpoints(Enum):
    """Danh sách các endpoint của API-Football v3"""
    TIMEZONES = "/timezone"
    COUNTRIES = "/countries"
    LEAGUES = "/leagues"
    LEAGUES_SEASONS = "/leagues/seasons"
    FIXTURES = "/fixtures"
    FIXTURES_ROUNDS = "/fixtures/rounds"
    FIXTURES_HEADTOHEAD = "/fixtures/headtohead"
    FIXTURES_EVENTS = "/fixtures/events"
    FIXTURES_STATISTICS = "/fixtures/statistics"
    FIXTURES_LINEUPS = "/fixtures/lineups"
    FIXTURES_PLAYERS = "/fixtures/players"
    TEAMS = "/teams"
    TEAMS_STATISTICS = "/teams/statistics"
    TEAMS_SEASONS = "/teams/seasons"
    TEAMS_COUNTRIES = "/teams/countries"
    PLAYERS = "/players"
    PLAYERS_SEASONS = "/players/seasons"
    PLAYERS_SQUADS = "/players/squads"
    PLAYERS_TOPSCORERS = "/players/topscorers"
    PLAYERS_TOPASSISTS = "/players/topassists"
    PLAYERS_TOPYELLOWCARDS = "/players/topyellowcards"
    PLAYERS_TOPREDCARDS = "/players/topredcards"
    STANDINGS = "/standings"
    VENUES = "/venues"
    COACHES = "/coachs"  
    TRANSFERS = "/transfers"
    TROPHIES = "/trophies"
    SIDELINED = "/sidelined"
    ODDS = "/odds"
    ODDS_MAPPING = "/odds/mapping"
    ODDS_BOOKMAKERS = "/odds/bookmakers"
    ODDS_BETS = "/odds/bets"
    ODDS_LIVE = "/odds/live"
    ODDS_LIVE_BETS = "/odds/live/bets"
    INJURIES = "/injuries"
    PREDICTIONS = "/predictions"

    @classmethod
    def from_string(cls, value: str):
        """
        Chuyển đổi chuỗi thành Enum member (case-insensitive key lookup).
        """
        if not isinstance(value, str):
            raise ValueError(f"Endpoint key phải là string, nhận: {type(value)}")
        key = value.strip().upper()
        try:
            return cls[key]
        except KeyError:
            valid = ', '.join(cls.__members__.keys())
            raise ValueError(f"Invalid endpoint: {value!r}. Valid keys: {valid}")

class APIFootballConfig:
    """
    Cấu hình cơ bản cho API-Football: BASE_URL, rate limits và headers.
    """
    BASE_URL = "https://v3.football.api-sports.io"

    # Rate limits (requests per second) theo đặc tả của API
    # Lưu ý: Giá trị này có thể cần điều chỉnh theo plan subscription
    RATE_LIMITS = {
        "DEFAULT": 1,  # Conservative default - adjust based on your plan
        "PREMIUM": 10,  # For premium subscriptions
        # Các endpoint live (cập nhật liên tục) có giới hạn thấp hơn
        "FIXTURES_LIVE": 1,
        "ODDS_LIVE": 1
    }

    # API key (dùng direct API-Football)
    API_KEY = os.getenv("API_FOOTBALL_KEY", "")

    # Header mặc định cho direct API-Football
    DEFAULT_HEADERS = {
        "x-apisports-key": API_KEY,
        "Accept-Encoding": "gzip"
    }

    @classmethod
    def validate_config(cls):
        """Validate configuration settings"""
        if not cls.API_KEY:
            raise ValueError("API_FOOTBALL_KEY environment variable is required")
        return True

# Mapping endpoint path → rate limit group
RATE_LIMIT_ENDPOINT_MAPPING = {
    APIFootballEndpoints.FIXTURES.value: "FIXTURES_LIVE",
    APIFootballEndpoints.FIXTURES_EVENTS.value: "FIXTURES_LIVE",
    APIFootballEndpoints.FIXTURES_STATISTICS.value: "FIXTURES_LIVE",
    APIFootballEndpoints.FIXTURES_LINEUPS.value: "FIXTURES_LIVE",
    APIFootballEndpoints.FIXTURES_PLAYERS.value: "FIXTURES_LIVE",
    APIFootballEndpoints.ODDS_LIVE.value: "ODDS_LIVE",
    APIFootballEndpoints.ODDS_LIVE_BETS.value: "ODDS_LIVE"
}


def build_url(endpoint: APIFootballEndpoints, params: dict = None) -> str:
    """
    Xây dựng URL đầy đủ cho yêu cầu API.
    - endpoint: member của APIFootballEndpoints
    - params: dict các tham số query string
    """
    if not isinstance(endpoint, APIFootballEndpoints):
        raise TypeError(f"endpoint phải là APIFootballEndpoints, nhận: {type(endpoint)}")
    
    base = APIFootballConfig.BASE_URL.rstrip('/')
    url = f"{base}{endpoint.value}"
    
    if params:
        # Filter out None values and empty strings
        clean_params = {k: v for k, v in params.items() if v is not None and v != ""}
        if clean_params:
            qs = urlencode(clean_params, doseq=True)
            url = f"{url}?{qs}"
    
    return url


def get_rate_limit(endpoint: APIFootballEndpoints) -> int:
    """
    Lấy giới hạn requests/giây cho endpoint.
    Nếu không có quy định riêng, trả về DEFAULT.
    """
    if not isinstance(endpoint, APIFootballEndpoints):
        raise TypeError(f"endpoint phải là APIFootballEndpoints, nhận: {type(endpoint)}")
    
    key = RATE_LIMIT_ENDPOINT_MAPPING.get(endpoint.value, "DEFAULT")
    limit = APIFootballConfig.RATE_LIMITS.get(key, APIFootballConfig.RATE_LIMITS["DEFAULT"])
    
    try:
        val = int(limit)
        return max(val, 1)  # Minimum 1 request per second
    except (ValueError, TypeError):
        return APIFootballConfig.RATE_LIMITS["DEFAULT"]


def is_live_endpoint(endpoint: APIFootballEndpoints) -> bool:
    """
    Kiểm tra xem endpoint có phải là live endpoint không.
    Live endpoints thường có rate limit thấp hơn.
    """
    live_endpoints = {
        APIFootballEndpoints.FIXTURES,
        APIFootballEndpoints.FIXTURES_EVENTS,
        APIFootballEndpoints.FIXTURES_STATISTICS,
        APIFootballEndpoints.FIXTURES_LINEUPS,
        APIFootballEndpoints.FIXTURES_PLAYERS,
        APIFootballEndpoints.ODDS_LIVE,
        APIFootballEndpoints.ODDS_LIVE_BETS
    }
    return endpoint in live_endpoints