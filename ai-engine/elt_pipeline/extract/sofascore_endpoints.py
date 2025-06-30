# ai-engine\elt_pipeline\extract\sofascore_endpoints.py

import logging
import re
from enum import Enum
from typing import Dict, Any, Optional, Tuple, Set
from urllib.parse import urlencode
from functools import lru_cache

# Import các thành phần cấu hình cần thiết
from config.settings import SofascoreSettings

logger = logging.getLogger(__name__)

class SofaScoreEndpoints(Enum):
    """
    SofaScore API endpoints - chỉ chứa endpoint paths.
    
    Tất cả endpoints được verify với SofaScore API thực tế.
    Tuân thủ Single Responsibility Principle - chỉ định nghĩa endpoints.
    """
    
    # === Core Match Endpoints ===
    MATCH_DETAIL = "/event/{match_id}/details"
    MATCH_LINEUPS = "/event/{match_id}/lineups"  
    MATCH_STATISTICS = "/event/{match_id}/statistics"
    MATCH_INCIDENTS = "/event/{match_id}/incidents"
    MATCH_H2H = "/event/{match_id}/h2h/events"
    MATCH_GRAPH = "/event/{match_id}/graph"
    MATCH_MOMENTUM = "/event/{match_id}/momentum"
    MATCH_HEATMAP = "/event/{match_id}/heatmap/{team_id}"
    MATCH_SHOTMAP = "/event/{match_id}/shotmap"
    MATCH_HIGHLIGHTS = "/event/{match_id}/highlights"
    
    # === Tournament/Season Endpoints ===
    TOURNAMENT_INFO = "/unique-tournament/{tournament_id}"
    TOURNAMENT_SEASONS = "/unique-tournament/{tournament_id}/seasons"
    TOURNAMENT_CATEGORIES = "/unique-tournament/{tournament_id}/categories"
    TOURNAMENT_MEDIA = "/unique-tournament/{tournament_id}/media"
    
    # === Season-specific Endpoints ===
    SEASON_STANDINGS = "/unique-tournament/{tournament_id}/season/{season_id}/standings/total"
    SEASON_MATCHES_LAST = "/unique-tournament/{tournament_id}/season/{season_id}/events/last/{page}"
    SEASON_MATCHES_NEXT = "/unique-tournament/{tournament_id}/season/{season_id}/events/next/{page}"
    SEASON_MATCHES_ROUND = "/unique-tournament/{tournament_id}/season/{season_id}/events/round/{round}"
    SEASON_TOP_PLAYERS = "/unique-tournament/{tournament_id}/season/{season_id}/top-players/{type}"
    SEASON_STATISTICS = "/unique-tournament/{tournament_id}/season/{season_id}/statistics"
    
    # === Team Endpoints ===
    TEAM_INFO = "/team/{team_id}"
    TEAM_DETAILS = "/team/{team_id}/details"
    TEAM_PLAYERS = "/team/{team_id}/players"
    TEAM_MATCHES_LAST = "/team/{team_id}/events/last/{page}"
    TEAM_MATCHES_NEXT = "/team/{team_id}/events/next/{page}"
    TEAM_STATISTICS = "/team/{team_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
    TEAM_STATISTICS_BREAKDOWN = "/team/{team_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/breakdown"
    TEAM_TRANSFERS = "/team/{team_id}/transfers"
    TEAM_MEDIA = "/team/{team_id}/media"
    
    # === Player Endpoints ===
    PLAYER_INFO = "/player/{player_id}"
    PLAYER_DETAILS = "/player/{player_id}/details"
    PLAYER_STATISTICS = "/player/{player_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
    PLAYER_SEASON_STATS = "/player/{player_id}/statistics/seasons"
    PLAYER_CHARACTERISTICS = "/player/{player_id}/characteristics"
    PLAYER_TRANSFERS = "/player/{player_id}/transfers"
    PLAYER_MEDIA = "/player/{player_id}/media"
    PLAYER_MATCHES = "/player/{player_id}/events/last/{page}"
    
    # === Live Data Endpoints ===
    LIVE_MATCHES = "/sport/{sport_id}/events/live"
    LIVE_MATCH_TRACKER = "/event/{match_id}/tracker"
    
    # === Search Endpoints ===
    SEARCH_ALL = "/search/all"
    SEARCH = "/search/{query}"
    
    # === General Endpoints ===
    CATEGORIES = "/sport/{sport_id}/categories"
    SPORTS = "/sport"

    @classmethod
    def from_string(cls, value: str) -> 'SofaScoreEndpoints':
        """
        Chuyển đổi chuỗi thành Enum member (case-insensitive key lookup).
        
        Args:
            value: Tên endpoint key
            
        Returns:
            SofaScoreEndpoints: Endpoint enum member
            
        Raises:
            ValueError: Nếu endpoint key không hợp lệ
        """
        if not isinstance(value, str):
            raise ValueError(f"Endpoint key phải là string, nhận: {type(value)}")
        
        key = value.strip().upper()
        try:
            return cls[key]
        except KeyError:
            valid_keys = ', '.join(sorted(cls.__members__.keys()))
            raise ValueError(f"Invalid endpoint: {value!r}. Valid keys: {valid_keys}")

    @lru_cache(maxsize=None)
    def get_required_params(self) -> Set[str]:
        """
        Extract required parameters from endpoint path.
        
        Returns:
            Set[str]: Set of required parameter names
        """
        return set(re.findall(r'\{(\w+)\}', self.value))
    
    def has_param(self, param: str) -> bool:
        """
        Check if endpoint requires specific parameter.
        
        Args:
            param: Parameter name to check
            
        Returns:
            bool: True if parameter is required
        """
        return param in self.get_required_params()

class EndpointCategory(Enum):
    """
    Phân loại các endpoint theo chức năng để áp dụng rate limiting và timeout phù hợp.
    """
    LIVE = "live"
    SEARCH = "search" 
    MEDIA = "media"
    STANDARD = "standard"

# Mapping endpoint → category để áp dụng rate limiting
_ENDPOINT_CATEGORY_MAPPING = {
    # Live endpoints - cần real-time data, rate limit thấp
    SofaScoreEndpoints.LIVE_MATCHES: EndpointCategory.LIVE,
    SofaScoreEndpoints.LIVE_MATCH_TRACKER: EndpointCategory.LIVE,
    SofaScoreEndpoints.MATCH_MOMENTUM: EndpointCategory.LIVE,
    SofaScoreEndpoints.MATCH_INCIDENTS: EndpointCategory.LIVE,
    
    # Search endpoints - thường có rate limit nghiêm ngặt
    SofaScoreEndpoints.SEARCH_ALL: EndpointCategory.SEARCH,
    SofaScoreEndpoints.SEARCH: EndpointCategory.SEARCH,
    
    # Media endpoints - có thể cho phép rate cao hơn, cần timeout lớn
    SofaScoreEndpoints.TOURNAMENT_MEDIA: EndpointCategory.MEDIA,
    SofaScoreEndpoints.TEAM_MEDIA: EndpointCategory.MEDIA,
    SofaScoreEndpoints.PLAYER_MEDIA: EndpointCategory.MEDIA,
    SofaScoreEndpoints.MATCH_HIGHLIGHTS: EndpointCategory.MEDIA,
    SofaScoreEndpoints.MATCH_HEATMAP: EndpointCategory.MEDIA,
    SofaScoreEndpoints.MATCH_SHOTMAP: EndpointCategory.MEDIA,
}

def get_endpoint_category(endpoint: SofaScoreEndpoints) -> EndpointCategory:
    """
    Xác định category của endpoint để áp dụng rate limiting phù hợp.
    
    Args:
        endpoint: SofaScore endpoint
        
    Returns:
        EndpointCategory: Category của endpoint
        
    Raises:
        TypeError: Nếu endpoint không phải SofaScoreEndpoints
    """
    if not isinstance(endpoint, SofaScoreEndpoints):
        raise TypeError(f"endpoint phải là SofaScoreEndpoints, nhận: {type(endpoint)}")
    
    return _ENDPOINT_CATEGORY_MAPPING.get(endpoint, EndpointCategory.STANDARD)

def is_live_endpoint(endpoint: SofaScoreEndpoints) -> bool:
    """
    Kiểm tra xem endpoint có phải là live endpoint không.
    
    Args:
        endpoint: SofaScore endpoint
        
    Returns:
        bool: True nếu là live endpoint
        
    Raises:
        TypeError: Nếu endpoint không phải SofaScoreEndpoints
    """
    if not isinstance(endpoint, SofaScoreEndpoints):
        raise TypeError(f"endpoint phải là SofaScoreEndpoints, nhận: {type(endpoint)}")
    
    return get_endpoint_category(endpoint) == EndpointCategory.LIVE

def is_media_endpoint(endpoint: SofaScoreEndpoints) -> bool:
    """
    Kiểm tra xem endpoint có phải là media endpoint không.
    
    Args:
        endpoint: SofaScore endpoint
        
    Returns:
        bool: True nếu là media endpoint
        
    Raises:
        TypeError: Nếu endpoint không phải SofaScoreEndpoints
    """
    if not isinstance(endpoint, SofaScoreEndpoints):
        raise TypeError(f"endpoint phải là SofaScoreEndpoints, nhận: {type(endpoint)}")
    
    return get_endpoint_category(endpoint) == EndpointCategory.MEDIA

def validate_endpoint_params(endpoint: SofaScoreEndpoints, **kwargs) -> Dict[str, Any]:
    """
    Validate required parameters for endpoint.
    
    Args:
        endpoint: SofaScore endpoint
        **kwargs: Parameters to validate
        
    Returns:
        Dict[str, Any]: Validated parameters
        
    Raises:
        TypeError: If endpoint is not SofaScoreEndpoints
        ValueError: If required parameters are missing or invalid
    """
    if not isinstance(endpoint, SofaScoreEndpoints):
        raise TypeError(f"endpoint must be SofaScoreEndpoints, got: {type(endpoint)}")
    
    required_params = endpoint.get_required_params()
    validated_params = {}
    
    # Check all required parameters are provided
    missing_params = required_params - set(kwargs.keys())
    if missing_params:
        raise ValueError(
            f"Missing required parameters for {endpoint.name}: {', '.join(missing_params)}"
        )
    
    # Validate parameter types and values
    for param in required_params:
        value = kwargs[param]
        
        if param.endswith('_id'):
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"Parameter '{param}' must be positive integer, got: {value}")
        elif param in ('page', 'round'):
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"Parameter '{param}' must be non-negative integer, got: {value}")
        elif param == 'query':
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Parameter '{param}' must be non-empty string, got: {value}")
            value = value.strip()
        elif param == 'type':
            # For top players endpoint type validation
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Parameter '{param}' must be non-empty string, got: {value}")
            value = value.strip()
            
        validated_params[param] = value
    
    return validated_params

def _get_config():
    """
    Lazy import và cache config để tránh circular import.
    
    Returns:
        ConfigManager: Configuration instance
        
    Raises:
        ImportError: Nếu không thể import config
    """
    try:
        from config.settings import get_config
        return get_config()
    except ImportError as e:
        logging.error(f"Cannot import config: {e}")
        raise ImportError("Cannot access configuration. Ensure settings module is available.") from e


@lru_cache(maxsize=1)
def _get_base_url() -> str:
    """
    Lấy base URL từ configuration với caching.
    
    Returns:
        str: Base URL from configuration
        
    Note:
        Tuân thủ Single Source of Truth - chỉ lấy từ settings.py
    """
    try:
        config = _get_config()
        return str(config.sofascore.base_url).rstrip('/')
    except Exception as e:
        logging.error(f"Error getting base URL from config: {e}")
        raise RuntimeError("Cannot retrieve base URL from configuration") from e

def get_rate_limit_per_second(endpoint: SofaScoreEndpoints) -> int:
    """
    Lấy rate limit (requests/second) cho endpoint từ configuration.
    
    Args:
        endpoint: SofaScore endpoint
        
    Returns:
        int: Rate limit in requests per second
        
    Raises:
        TypeError: Nếu endpoint không phải SofaScoreEndpoints
    """
    if not isinstance(endpoint, SofaScoreEndpoints):
        raise TypeError(f"endpoint phải là SofaScoreEndpoints, nhận: {type(endpoint)}")
    
    try:
        config = _get_config()
        
        # Convert requests_per_minute to requests_per_second
        requests_per_minute = config.sofascore.requests_per_minute
        base_rate_per_second = max(1, requests_per_minute // 60)
        
        # Áp dụng modifier theo category
        category = get_endpoint_category(endpoint)
        
        if category == EndpointCategory.LIVE:
            # Live endpoints: giảm 50% để tránh overload
            return max(1, base_rate_per_second // 2)
        elif category == EndpointCategory.SEARCH:
            # Search endpoints: giảm 75% vì thường có rate limit nghiêm ngặt
            return max(1, base_rate_per_second // 4)
        elif category == EndpointCategory.MEDIA:
            # Media endpoints: có thể tăng 50% vì ít sensitive hơn
            return base_rate_per_second + max(1, base_rate_per_second // 2)
        else:
            # Standard endpoints
            return base_rate_per_second
            
    except Exception as e:
        logging.warning(f"Error getting rate limit from config: {e}. Using default.")
        return 1  # Safe default


def get_timeout_settings(endpoint: SofaScoreEndpoints) -> Tuple[int, int]:
    """
    Lấy timeout settings (connect_timeout, read_timeout) cho endpoint từ configuration.
    
    Args:
        endpoint: SofaScore endpoint
        
    Returns:
        Tuple[int, int]: (connect_timeout, read_timeout) in seconds
        
    Raises:
        TypeError: Nếu endpoint không phải SofaScoreEndpoints
    """
    if not isinstance(endpoint, SofaScoreEndpoints):
        raise TypeError(f"endpoint phải là SofaScoreEndpoints, nhận: {type(endpoint)}")
    
    try:
        config = _get_config()
        connect_timeout = config.scraping.connect_timeout
        read_timeout = config.scraping.read_timeout
        
        # Điều chỉnh timeout theo category
        category = get_endpoint_category(endpoint)
        
        if category == EndpointCategory.LIVE:
            # Live endpoints: timeout ngắn hơn để real-time
            return (connect_timeout // 2, read_timeout // 2)
        elif category == EndpointCategory.MEDIA:
            # Media endpoints: timeout dài hơn cho việc download
            return (connect_timeout, read_timeout * 2)
        else:
            # Standard và Search endpoints
            return (connect_timeout, read_timeout)
            
    except Exception as e:
        logging.warning(f"Error getting timeout from config: {e}. Using defaults.")
        return (10, 30)  # Safe defaults


def get_headers(endpoint: SofaScoreEndpoints, referer: Optional[str] = None) -> Dict[str, str]:
    """
    Lấy headers cho request từ configuration với randomization.
    
    Args:
        endpoint: SofaScore endpoint
        referer: Optional referer URL
        
    Returns:
        Dict[str, str]: Request headers
        
    Raises:
        TypeError: Nếu endpoint không phải SofaScoreEndpoints
    """
    if not isinstance(endpoint, SofaScoreEndpoints):
        raise TypeError(f"endpoint phải là SofaScoreEndpoints, nhận: {type(endpoint)}")
    
    try:
        config = _get_config()
        return config.sofascore.get_headers(referer=referer)
    except Exception as e:
        logging.warning(f"Error getting headers from config: {e}. Using minimal headers.")
        # Fallback headers - minimal để không fail request
        return {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }


def build_url(
    endpoint: SofaScoreEndpoints, 
    params: Optional[Dict[str, Any]] = None, 
    **kwargs
) -> str:
    """
    Xây dựng URL đầy đủ cho yêu cầu API SofaScore.
    
    Args:
        endpoint: SofaScore endpoint enum member
        params: Dict các tham số query string
        **kwargs: Các tham số để format vào URL path (tournament_id, match_id, etc.)
    
    Returns:
        str: URL đầy đủ
    
    Raises:
        TypeError: Nếu endpoint không phải SofaScoreEndpoints
        ValueError: Nếu thiếu tham số bắt buộc để format URL
        RuntimeError: Nếu không thể lấy base URL từ config
    """
    if not isinstance(endpoint, SofaScoreEndpoints):
        raise TypeError(f"endpoint phải là SofaScoreEndpoints, nhận: {type(endpoint)}")
    
    # Lấy base URL từ configuration (Single Source of Truth)
    base_url = _get_base_url()
    
    try:
        # Format URL path với các tham số từ kwargs
        path = endpoint.value.format(**kwargs)
    except KeyError as e:
        missing_param = str(e).strip("'")
        raise ValueError(
            f"Thiếu tham số bắt buộc '{missing_param}' để format endpoint {endpoint.name}"
        ) from e
    
    full_url = f"{base_url}{path}"
    
    # Thêm query parameters nếu có
    if params:
        # Filter out None values và empty strings - Clean Code principle
        clean_params = {
            k: v for k, v in params.items() 
            if v is not None and v != ""
        }
        if clean_params:
            query_string = urlencode(clean_params, doseq=True)
            full_url = f"{full_url}?{query_string}"
    
    return full_url

def requires_auth(endpoint: SofaScoreEndpoints) -> bool:
    """
    Kiểm tra xem endpoint có cần authentication không.
    
    Args:
        endpoint: SofaScore endpoint
        
    Returns:
        bool: True nếu cần authentication
        
    Raises:
        TypeError: Nếu endpoint không phải SofaScoreEndpoints
        
    Note:
        Hiện tại SofaScore public API không yêu cầu auth cho hầu hết endpoints.
        Hàm này để chuẩn bị cho tương lai nếu có premium endpoints.
    """
    if not isinstance(endpoint, SofaScoreEndpoints):
        raise TypeError(f"endpoint phải là SofaScoreEndpoints, nhận: {type(endpoint)}")
    
    # Hiện tại không có endpoint nào cần auth
    # Có thể extend trong tương lai
    premium_endpoints = set()  # type: set[SofaScoreEndpoints]
    
    return endpoint in premium_endpoints


# Convenience functions cho các use cases phổ biến
def build_tournament_url(tournament_id: int, params: Optional[Dict[str, Any]] = None) -> str:
    """
    Convenience function để build URL cho tournament info.
    
    Args:
        tournament_id: ID của tournament
        params: Optional query parameters
        
    Returns:
        str: Tournament URL
        
    Raises:
        ValueError: Nếu tournament_id không hợp lệ
    """
    if not isinstance(tournament_id, int) or tournament_id <= 0:
        raise ValueError(f"tournament_id phải là integer dương, nhận: {tournament_id}")
    
    return build_url(SofaScoreEndpoints.TOURNAMENT_INFO, params, tournament_id=tournament_id)


def build_match_url(match_id: int, params: Optional[Dict[str, Any]] = None) -> str:
    """
    Convenience function để build URL cho match detail.
    
    Args:
        match_id: ID của match
        params: Optional query parameters
        
    Returns:
        str: Match URL
        
    Raises:
        ValueError: Nếu match_id không hợp lệ
    """
    if not isinstance(match_id, int) or match_id <= 0:
        raise ValueError(f"match_id phải là integer dương, nhận: {match_id}")
    
    return build_url(SofaScoreEndpoints.MATCH_DETAIL, params, match_id=match_id)

def build_team_url(team_id: int, params: Optional[Dict[str, Any]] = None) -> str:
    """
    Convenience function để build URL cho team info.
    
    Args:
        team_id: ID của team
        params: Optional query parameters
        
    Returns:
        str: Team URL
        
    Raises:
        ValueError: Nếu team_id không hợp lệ
    """
    if not isinstance(team_id, int) or team_id <= 0:
        raise ValueError(f"team_id phải là integer dương, nhận: {team_id}")
    
    return build_url(SofaScoreEndpoints.TEAM_INFO, params, team_id=team_id)


def build_player_url(player_id: int, params: Optional[Dict[str, Any]] = None) -> str:
    """
    Convenience function để build URL cho player info.
    
    Args:
        player_id: ID của player
        params: Optional query parameters
        
    Returns:
        str: Player URL
        
    Raises:
        ValueError: Nếu player_id không hợp lệ
    """
    if not isinstance(player_id, int) or player_id <= 0:
        raise ValueError(f"player_id phải là integer dương, nhận: {player_id}")
    
    return build_url(SofaScoreEndpoints.PLAYER_INFO, params, player_id=player_id)