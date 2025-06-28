# ai-engine\elt_pipeline\extract\sofascore_endpoints.py

import os
from urllib.parse import urlencode
from enum import Enum
from typing import Dict, Any, Optional

class SofaScoreEndpoints(Enum):
    """Danh sách các endpoint của SofaScore API"""
    
    # Tournament endpoints
    TOURNAMENT_INFO = "/unique-tournament/{tournament_id}"
    TOURNAMENT_SEASONS = "/unique-tournament/{tournament_id}/seasons"
    TOURNAMENT_CATEGORIES = "/unique-tournament/{tournament_id}/categories"
    TOURNAMENT_MEDIA = "/unique-tournament/{tournament_id}/media"
    
    # Season endpoints
    SEASON_STANDINGS = "/unique-tournament/{tournament_id}/season/{season_id}/standings/total"
    SEASON_MATCHES = "/unique-tournament/{tournament_id}/season/{season_id}/events/last/{page}"
    SEASON_MATCHES_ROUND = "/unique-tournament/{tournament_id}/season/{season_id}/events/round/{round}"
    SEASON_TOP_PLAYERS = "/unique-tournament/{tournament_id}/season/{season_id}/top-players/{type}"
    SEASON_STATISTICS = "/unique-tournament/{tournament_id}/season/{season_id}/statistics"
    
    # Match endpoints
    MATCH_DETAIL = "/event/{match_id}"
    MATCH_LINEUPS = "/event/{match_id}/lineups"
    MATCH_STATISTICS = "/event/{match_id}/statistics"
    MATCH_H2H = "/event/{match_id}/h2h/events"
    MATCH_INCIDENTS = "/event/{match_id}/incidents"
    MATCH_GRAPH = "/event/{match_id}/graph"
    MATCH_MOMENTUM = "/event/{match_id}/momentum"
    MATCH_HEATMAP = "/event/{match_id}/heatmap/{team_id}"
    MATCH_SHOTMAP = "/event/{match_id}/shotmap"
    MATCH_HIGHLIGHTS = "/event/{match_id}/highlights"
    
    # Team endpoints
    TEAM_INFO = "/team/{team_id}"
    TEAM_MATCHES = "/team/{team_id}/events/last/{page}"
    TEAM_MATCHES_NEXT = "/team/{team_id}/events/next/{page}"
    TEAM_STATISTICS = "/team/{team_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
    TEAM_STATISTICS_BREAKDOWN = "/team/{team_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/breakdown"
    TEAM_FORM = "/team/{team_id}/events/last/{page}"
    TEAM_TRANSFERS = "/team/{team_id}/transfers"
    TEAM_PLAYERS = "/team/{team_id}/players"
    TEAM_MEDIA = "/team/{team_id}/media"
    
    # Player endpoints
    PLAYER_INFO = "/player/{player_id}"
    PLAYER_STATISTICS = "/player/{player_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
    PLAYER_CHARACTERISTICS = "/player/{player_id}/characteristics"
    PLAYER_TRANSFERS = "/player/{player_id}/transfers"
    PLAYER_MEDIA = "/player/{player_id}/media"
    PLAYER_MATCHES = "/player/{player_id}/events/last/{page}"
    
    # Live data endpoints
    LIVE_MATCHES = "/sport/{sport_id}/events/live"
    LIVE_MATCH_TRACKER = "/event/{match_id}/tracker"
    
    # Search endpoints
    SEARCH = "/search/{query}"
    
    # Categories and sports
    CATEGORIES = "/sport/{sport_id}/categories"
    SPORTS = "/sport"

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


class SofaScoreConfig:
    """
    Cấu hình cơ bản cho SofaScore API: BASE_URL, rate limits và headers.
    """
    BASE_URL = "https://api.sofascore.com/api/v1"
    
    # Rate limits (requests per second)
    # SofaScore không công bố rate limit chính thức, nên dùng conservative values
    RATE_LIMITS = {
        "DEFAULT": 2,  # Conservative default
        "LIVE": 1,     # Live endpoints có thể nghiêm ngặt hơn
        "SEARCH": 1,   # Search endpoints thường có rate limit thấp
        "MEDIA": 3,    # Media endpoints có thể cho phép rate cao hơn
    }
    
    # Timeout settings (seconds)
    TIMEOUT_SETTINGS = {
        "CONNECT_TIMEOUT": 10,
        "READ_TIMEOUT": 30,
        "TOTAL_TIMEOUT": 60
    }
    
    # Headers mặc định cho SofaScore API
    DEFAULT_HEADERS = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.sofascore.com/",
        "Origin": "https://www.sofascore.com"
    }
    
    # API key (nếu có)
    API_KEY = os.getenv("SOFASCORE_API_KEY", "")
    
    @classmethod
    def get_headers(cls, include_api_key: bool = False) -> Dict[str, str]:
        """Lấy headers với tùy chọn bao gồm API key"""
        headers = cls.DEFAULT_HEADERS.copy()
        if include_api_key and cls.API_KEY:
            headers["Authorization"] = f"Bearer {cls.API_KEY}"
        return headers
    
    @classmethod
    def validate_config(cls):
        """Validate configuration settings"""
        if not cls.BASE_URL:
            raise ValueError("BASE_URL is required")
        if not isinstance(cls.RATE_LIMITS, dict):
            raise ValueError("RATE_LIMITS must be a dictionary")
        return True


# Mapping endpoint path → rate limit group
RATE_LIMIT_ENDPOINT_MAPPING = {
    # Live endpoints
    SofaScoreEndpoints.LIVE_MATCHES.value: "LIVE",
    SofaScoreEndpoints.LIVE_MATCH_TRACKER.value: "LIVE",
    SofaScoreEndpoints.MATCH_MOMENTUM.value: "LIVE",
    
    # Search endpoints
    SofaScoreEndpoints.SEARCH.value: "SEARCH",
    
    # Media endpoints
    SofaScoreEndpoints.TOURNAMENT_MEDIA.value: "MEDIA",
    SofaScoreEndpoints.TEAM_MEDIA.value: "MEDIA",
    SofaScoreEndpoints.PLAYER_MEDIA.value: "MEDIA",
    SofaScoreEndpoints.MATCH_HIGHLIGHTS.value: "MEDIA",
}


def build_url(endpoint: SofaScoreEndpoints, params: Optional[Dict[str, Any]] = None, **kwargs) -> str:
    """
    Xây dựng URL đầy đủ cho yêu cầu API SofaScore.
    
    Args:
        endpoint: member của SofaScoreEndpoints
        params: dict các tham số query string
        **kwargs: các tham số để format vào URL path (tournament_id, match_id, etc.)
    
    Returns:
        str: URL đầy đủ
    
    Raises:
        TypeError: nếu endpoint không phải SofaScoreEndpoints
        ValueError: nếu thiếu tham số bắt buộc để format URL
    """
    if not isinstance(endpoint, SofaScoreEndpoints):
        raise TypeError(f"endpoint phải là SofaScoreEndpoints, nhận: {type(endpoint)}")
    
    base = SofaScoreConfig.BASE_URL.rstrip('/')
    
    try:
        # Format URL path với các tham số từ kwargs
        path = endpoint.value.format(**kwargs)
    except KeyError as e:
        missing_param = str(e).strip("'")
        raise ValueError(f"Thiếu tham số bắt buộc '{missing_param}' để format endpoint {endpoint.name}")
    
    url = f"{base}{path}"
    
    # Thêm query parameters nếu có
    if params:
        # Filter out None values và empty strings
        clean_params = {k: v for k, v in params.items() if v is not None and v != ""}
        if clean_params:
            qs = urlencode(clean_params, doseq=True)
            url = f"{url}?{qs}"
    
    return url


def get_rate_limit(endpoint: SofaScoreEndpoints) -> int:
    """
    Lấy giới hạn requests/giây cho endpoint.
    Nếu không có quy định riêng, trả về DEFAULT.
    """
    if not isinstance(endpoint, SofaScoreEndpoints):
        raise TypeError(f"endpoint phải là SofaScoreEndpoints, nhận: {type(endpoint)}")
    
    # Tìm rate limit group cho endpoint
    endpoint_path = endpoint.value
    
    # Kiểm tra exact match trước
    if endpoint_path in RATE_LIMIT_ENDPOINT_MAPPING:
        key = RATE_LIMIT_ENDPOINT_MAPPING[endpoint_path]
    else:
        # Kiểm tra partial match cho các endpoint có template
        key = "DEFAULT"
        for mapped_path, rate_group in RATE_LIMIT_ENDPOINT_MAPPING.items():
            if _path_matches_template(endpoint_path, mapped_path):
                key = rate_group
                break
    
    limit = SofaScoreConfig.RATE_LIMITS.get(key, SofaScoreConfig.RATE_LIMITS["DEFAULT"])
    
    try:
        val = int(limit)
        return max(val, 1)  # Minimum 1 request per second
    except (ValueError, TypeError):
        return SofaScoreConfig.RATE_LIMITS["DEFAULT"]


def is_live_endpoint(endpoint: SofaScoreEndpoints) -> bool:
    """
    Kiểm tra xem endpoint có phải là live endpoint không.
    Live endpoints thường có rate limit thấp hơn và cần real-time data.
    """
    live_endpoints = {
        SofaScoreEndpoints.LIVE_MATCHES,
        SofaScoreEndpoints.LIVE_MATCH_TRACKER,
        SofaScoreEndpoints.MATCH_MOMENTUM,
        SofaScoreEndpoints.MATCH_INCIDENTS,
    }
    return endpoint in live_endpoints


def is_media_endpoint(endpoint: SofaScoreEndpoints) -> bool:
    """
    Kiểm tra xem endpoint có phải là media endpoint không.
    Media endpoints thường trả về URLs hoặc binary data.
    """
    media_endpoints = {
        SofaScoreEndpoints.TOURNAMENT_MEDIA,
        SofaScoreEndpoints.TEAM_MEDIA,
        SofaScoreEndpoints.PLAYER_MEDIA,
        SofaScoreEndpoints.MATCH_HIGHLIGHTS,
        SofaScoreEndpoints.MATCH_HEATMAP,
        SofaScoreEndpoints.MATCH_SHOTMAP,
    }
    return endpoint in media_endpoints


def requires_auth(endpoint: SofaScoreEndpoints) -> bool:
    """
    Kiểm tra xem endpoint có cần authentication không.
    Một số endpoint của SofaScore có thể cần API key hoặc authentication.
    """
    # Hiện tại SofaScore public API không yêu cầu auth cho hầu hết endpoints
    # Tuy nhiên có thể có một số endpoint premium cần auth
    premium_endpoints = {
        # Thêm các endpoint cần auth ở đây khi có thông tin
    }
    return endpoint in premium_endpoints


def get_timeout(endpoint: SofaScoreEndpoints) -> tuple:
    """
    Lấy timeout settings cho endpoint (connect_timeout, read_timeout).
    """
    config = SofaScoreConfig.TIMEOUT_SETTINGS
    
    # Live endpoints có thể cần timeout ngắn hơn
    if is_live_endpoint(endpoint):
        return (config["CONNECT_TIMEOUT"] // 2, config["READ_TIMEOUT"] // 2)
    
    # Media endpoints có thể cần timeout dài hơn
    if is_media_endpoint(endpoint):
        return (config["CONNECT_TIMEOUT"], config["READ_TIMEOUT"] * 2)
    
    return (config["CONNECT_TIMEOUT"], config["READ_TIMEOUT"])


def _path_matches_template(endpoint_path: str, template_path: str) -> bool:
    """
    Kiểm tra xem endpoint path có match với template path không.
    Helper function cho rate limit mapping.
    """
    # Simple template matching - có thể cải thiện thêm nếu cần
    endpoint_parts = endpoint_path.split('/')
    template_parts = template_path.split('/')
    
    if len(endpoint_parts) != len(template_parts):
        return False
    
    for ep, tp in zip(endpoint_parts, template_parts):
        if tp.startswith('{') and tp.endswith('}'):
            continue  # Template parameter, skip
        if ep != tp:
            return False
    
    return True


# Convenience functions cho các use cases phổ biến
def build_tournament_url(tournament_id: int, params: Optional[Dict] = None) -> str:
    """Convenience function để build URL cho tournament info"""
    return build_url(SofaScoreEndpoints.TOURNAMENT_INFO, params, tournament_id=tournament_id)


def build_match_url(match_id: int, params: Optional[Dict] = None) -> str:
    """Convenience function để build URL cho match detail"""
    return build_url(SofaScoreEndpoints.MATCH_DETAIL, params, match_id=match_id)


def build_team_url(team_id: int, params: Optional[Dict] = None) -> str:
    """Convenience function để build URL cho team info"""
    return build_url(SofaScoreEndpoints.TEAM_INFO, params, team_id=team_id)


def build_player_url(player_id: int, params: Optional[Dict] = None) -> str:
    """Convenience function để build URL cho player info"""
    return build_url(SofaScoreEndpoints.PLAYER_INFO, params, player_id=player_id)