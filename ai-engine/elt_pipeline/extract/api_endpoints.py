# ai-engine\elt_pipeline\extract\api_endpoints.py

import os
from urllib.parse import urlencode
from enum import Enum

class APIFootballEndpoints(Enum):
    """Danh sách các endpoint của API-Football theo tài liệu chính thức"""
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
    COACHES = "/coaches"
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
    MY_API_PLANS = "/my-api-plans"

    @classmethod
    def from_string(cls, value: str):
        """
        Chuyển đổi chuỗi thành Enum member.
        Hỗ trợ case-insensitive: sẽ strip và uppercase trước khi lookup.
        """
        if not isinstance(value, str):
            raise ValueError(f"Endpoint key phải là string, nhận: {type(value)}")
        key = value.strip().upper()
        try:
            return cls[key]
        except KeyError:
            raise ValueError(f"Invalid endpoint: {value!r}. Valid keys: {list(cls.__members__.keys())}")

class APIFootballConfig:
    """
    Cấu hình cơ bản cho API-Football: BASE_URL, rate limits.
    Nếu bạn gọi direct API-Football (không qua RapidAPI), HEADER sẽ dùng x-apisports-key.
    Nếu bạn gọi qua RapidAPI marketplace, client sẽ tự thêm x-rapidapi-key + x-rapidapi-host.
    """
    # Ví dụ BASE_URL của API-Football (direct):
    BASE_URL = "https://v3.football.api-sports.io"

    # Rate limits giả định: requests per second.
    # Bạn có thể điều chỉnh theo tài liệu API thực tế hoặc cấu hình từ ngoài.
    RATE_LIMITS = {
        "DEFAULT": 10,         # mặc định 10 req/s
        "FIXTURES_LIVE": 4,    # endpoint liên quan live fixtures giới hạn 4 req/s
    }

    # Nếu bạn dùng direct API-Football: có thể lấy 1 key từ env để test:
    # Nhưng trong client, thường dùng config.API.KEYS (list). Phần này chỉ làm ví dụ hoặc fallback.
    # Nếu không dùng hoặc không muốn raise ở đây, có thể bỏ phần raise.
    API_KEY = os.getenv("API_FOOTBALL_KEY")
    if not API_KEY:
        # Nếu bạn không cần enforce env ở đây, có thể comment dòng raise sau:
        # raise EnvironmentError("Missing API_FOOTBALL_KEY environment variable.")
        pass

    # DEFAULT_HEADERS chỉ là ví dụ: nếu direct, header dùng x-apisports-key.
    # Nếu gọi qua RapidAPI, client sẽ tự set header phù hợp, không phụ thuộc DEFAULT_HEADERS này.
    DEFAULT_HEADERS = {
        "x-apisports-key": API_KEY or "",
        # "x-rapidapi-host": "v3.football.api-sports.io",  # Chỉ dùng nếu gọi qua RapidAPI
        "Accept-Encoding": "gzip",
    }

# Mapping từ endpoint.value (chuỗi path) sang key trong RATE_LIMITS nếu cần khác default
RATE_LIMIT_ENDPOINT_MAPPING = {
    APIFootballEndpoints.FIXTURES.value: "FIXTURES_LIVE",
    APIFootballEndpoints.FIXTURES_EVENTS.value: "FIXTURES_LIVE",
    APIFootballEndpoints.FIXTURES_STATISTICS.value: "FIXTURES_LIVE",
    APIFootballEndpoints.FIXTURES_LINEUPS.value: "FIXTURES_LIVE",
    APIFootballEndpoints.FIXTURES_PLAYERS.value: "FIXTURES_LIVE",
    APIFootballEndpoints.ODDS_LIVE.value: "FIXTURES_LIVE",
    APIFootballEndpoints.ODDS_LIVE_BETS.value: "FIXTURES_LIVE",
    # Nếu cần map thêm, bổ sung tương tự
}

def build_url(endpoint: APIFootballEndpoints, params: dict = None) -> str:
    """
    Xây dựng URL đầy đủ cho yêu cầu API.
    - endpoint: Enum APIFootballEndpoints
    - params: dict tham số query string
    """
    if not isinstance(endpoint, APIFootballEndpoints):
        raise TypeError(f"endpoint phải là APIFootballEndpoints, nhận: {type(endpoint)}")
    path = endpoint.value
    base = APIFootballConfig.BASE_URL.rstrip("/")  # đảm bảo không dư slash
    url = f"{base}{path}"
    if params:
        # urlencode với doseq=True để hỗ trợ list params
        query = urlencode(params, doseq=True)
        url = f"{url}?{query}"
    return url

def get_rate_limit(endpoint: APIFootballEndpoints) -> int:
    """
    Lấy giới hạn requests/giây cho endpoint cụ thể.
    Nếu không có mapping riêng, trả về DEFAULT.
    """
    if not isinstance(endpoint, APIFootballEndpoints):
        raise TypeError(f"endpoint phải là APIFootballEndpoints, nhận: {type(endpoint)}")
    key = RATE_LIMIT_ENDPOINT_MAPPING.get(endpoint.value, "DEFAULT")
    # đảm bảo luôn có giá trị > 0; nếu không tìm thấy, fallback DEFAULT
    limit = APIFootballConfig.RATE_LIMITS.get(key)
    if limit is None:
        limit = APIFootballConfig.RATE_LIMITS.get("DEFAULT", 1)
    # Nếu limit <= 0, đặt lại thành 1 để tránh ZeroDivisionError
    if not isinstance(limit, (int, float)) or limit <= 0:
        limit = APIFootballConfig.RATE_LIMITS.get("DEFAULT", 1)
    return limit
