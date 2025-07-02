# ai-engine\config\settings.py

from pydantic import Field, AnyUrl, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import os
import pytz
import logging
import urllib.parse
import random
from datetime import datetime, timezone

ENV_FILE_PATH = (Path(__file__).parent.parent / ".env").resolve()
if not ENV_FILE_PATH.exists():
    logging.warning(f".env file not found at {ENV_FILE_PATH}. Using default values or environment variables.")
    
class DatabaseSettings(BaseSettings):
    """Cấu hình database với validation an toàn"""
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    host: str = Field(default="localhost")
    port: int = Field(default=5432, gt=0, le=65535)
    dbname: str = Field(default="premier_league", min_length=1)
    user: str = Field(default="postgres", min_length=1)
    password: str = Field(default="")

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate hostname/IP format"""
        if not v or v.isspace():
            raise ValueError("Database host cannot be empty")
        return v.strip()

    @property
    def dsn(self) -> str:
        """Tạo connection string an toàn cho PostgreSQL với URL encoding"""
        pwd = self.password
        user_enc = urllib.parse.quote(self.user, safe="")
        pwd_enc = urllib.parse.quote(pwd, safe="")
        host_enc = urllib.parse.quote(self.host, safe="")
        db_enc = urllib.parse.quote(self.dbname, safe="")
        
        return f"postgresql://{user_enc}:{pwd_enc}@{host_enc}:{self.port}/{db_enc}"

    @property
    def is_configured(self) -> bool:
        """Kiểm tra database có được cấu hình đầy đủ không"""
        return bool(self.host and self.user and self.dbname and self.password)

class APIFootballSettings(BaseSettings):
    """Cấu hình API Football với multiple keys và rotation (legacy support)"""
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    base_url: AnyUrl = Field(
        default="https://v3.football.api-sports.io",
        env="API_FOOTBALL_BASE_URL"
    )
    api_keys: List[str] = Field(
        default_factory=list, 
        env="API_FOOTBALL_KEY"
    )  # Changed from List[SecretStr] to List[str]
    
    # Rate limiting config
    requests_per_minute: int = Field(default=100, env="API_RATE_LIMIT", gt=0)
    
    @field_validator("base_url")
    @classmethod
    def validate_https(cls, value: AnyUrl) -> AnyUrl:
        """Đảm bảo chỉ sử dụng HTTPS cho bảo mật"""
        if not value or str(value).strip() == "":
            raise ValueError("API base URL cannot be empty")
        if value.scheme != "https":
            raise ValueError("API base URL must use HTTPS for security")
        return value

    @field_validator("api_keys", mode="before")
    @classmethod
    def parse_api_keys(cls, value) -> List[str]:
        # print("DEBUG validator input:", value, type(value))
        """Xử lý nhiều định dạng API keys từ string hoặc list"""
        if not value:
            return []
        # print(f"Test{value}")
        if isinstance(value, str):
            # Hỗ trợ cả comma và semicolon separators
            keys = []
            for separator in [",", ";"]:
                if separator in value:
                    keys = [k.strip() for k in value.split(separator) if k.strip()]
                    break
            else:
                # Single key
                keys = [value.strip()] if value.strip() else []
            return [k for k in keys if k]
        if isinstance(value, list):
            result = []
            for v in value:
                if isinstance(v, str):
                    result.append(v.strip())
                elif v and str(v).strip():
                    result.append(str(v).strip())
            return result
        return []

    def get_random_key(self) -> str:
        """Lấy ngẫu nhiên một API key với thread-safe rotation"""
        if not self.api_keys:
            raise ValueError("No API keys available - check API_FOOTBALL_KEY environment variable")
        key = random.choice(self.api_keys)
        # Safe logging - chỉ log masked version
        if len(key) > 8:
            masked_key = f"{key[:4]}...{key[-4:]}"
        else:
            masked_key = f"{key[:2]}...{key[-2:]}" if len(key) > 4 else "***"
        try:
            logging.debug(f"Using API key: {masked_key}")
        except:
            pass
        return key

    @property
    def is_configured(self) -> bool:
        """Kiểm tra API có được cấu hình đầy đủ không"""
        return bool(self.base_url and self.api_keys)

class SofascoreSettings(BaseSettings):
    """Cấu hình Sofascore API không chính thức - Enhanced for scraping"""
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Base URLs cho các endpoints khác nhau
    base_url: AnyUrl = Field(
        default="https://api.sofascore.com/api/v1",
        env="SOFASCORE_BASE_URL"
    )
    
    # Web URLs cho scraping fallback
    web_base_url: AnyUrl = Field(
        default="https://www.sofascore.com",
        env="SOFASCORE_WEB_URL"
    )
    
    # Premier League tournament ID trên Sofascore
    premier_league_id: int = Field(default=17, env="SOFASCORE_EPL_ID")
    
    # Rate limiting để tránh bị block
    requests_per_minute: int = Field(default=30, env="SOFASCORE_RATE_LIMIT", gt=0)  # Giảm xuống để an toàn
    delay_between_requests: float = Field(default=2.0, env="SOFASCORE_DELAY", ge=0.5)  # Tăng delay
    
    # Retry configuration - Enhanced
    max_retries: int = Field(default=5, env="SOFASCORE_MAX_RETRIES", ge=1)  # Tăng retries
    retry_delay: float = Field(default=3.0, env="SOFASCORE_RETRY_DELAY", ge=1.0)  # Tăng delay
    exponential_backoff: bool = Field(default=True, env="SOFASCORE_EXPONENTIAL_BACKOFF")
    
    # Circuit breaker để tránh spam requests
    circuit_breaker_threshold: int = Field(default=5, env="SOFASCORE_CIRCUIT_THRESHOLD", ge=3)
    circuit_breaker_timeout: int = Field(default=300, env="SOFASCORE_CIRCUIT_TIMEOUT", ge=60)  # 5 minutes
    
    # Headers rotation để tránh detection - Enhanced
    user_agents: List[str] = Field(
        default_factory=lambda: [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0"
        ],
        env="SOFASCORE_USER_AGENTS",
        description="Danh sách User-Agent để xoay vòng, phân tách bằng dấu ; hoặc newline."
    )
    
    # Accept languages for better disguise
    accept_languages: List[str] = Field(
        default_factory=lambda: [
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "en-US,en;q=0.8,vi;q=0.6",
            "en-GB,en-US;q=0.9,en;q=0.8"
        ],
        env="SOFASCORE_ACCEPT_LANGUAGES",
        description="Danh sách Accept-Language để xoay vòng, phân tách bằng dấu ; hoặc newline."
    )
    
    # Session management
    session_rotation_interval: int = Field(default=100, env="SOFASCORE_SESSION_ROTATION", gt=0)  # Rotate session sau N requests
    enable_cookies: bool = Field(default=True, env="SOFASCORE_ENABLE_COOKIES")
    
    @field_validator("base_url", "web_base_url")
    @classmethod
    def validate_https(cls, value: AnyUrl) -> AnyUrl:
        """Đảm bảo chỉ sử dụng HTTPS cho bảo mật"""
        if not value or str(value).strip() == "":
            raise ValueError("Sofascore URL cannot be empty")
        if value.scheme != "https":
            raise ValueError("Sofascore URL must use HTTPS for security")
        return value

    @field_validator("user_agents", "accept_languages", mode="before")
    @classmethod
    def parse_string_list(cls, value, field_info) -> List[str]:
        """Parse user agents/languages từ string hoặc list"""
        field_name = getattr(field_info, 'field_name', 'unknown')
        
        # Get default values
        if field_name == "user_agents":
            default_value = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0"
            ]
        else:  # accept_languages
            default_value = [
                "en-US,en;q=0.9",
                "en-GB,en;q=0.9",
                "en-US,en;q=0.8,vi;q=0.6",
                "en-GB,en-US;q=0.9,en;q=0.8"
            ]
        
        if not value:
            return default_value
        
        if isinstance(value, str):
            # Split by semicolon hoặc newline
            items = []
            for separator in [";", "\n", "|"]:
                if separator in value:
                    items = [item.strip() for item in value.split(separator) if item.strip()]
                    break
            else:
                items = [value.strip()] if value.strip() else []
            return items if items else default_value
        
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        
        return default_value

    def get_random_user_agent(self) -> str:
        """Lấy ngẫu nhiên một User-Agent"""
        return random.choice(self.user_agents)
    
    def get_random_accept_language(self) -> str:
        """Lấy ngẫu nhiên một Accept-Language"""
        return random.choice(self.accept_languages)

    def get_headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        """Tạo headers cho request với randomization"""
        headers = {
            "User-Agent": self.get_random_user_agent(),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": self.get_random_accept_language(),
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
        
        if referer:
            headers["Referer"] = referer
        
        # Random DNT header
        if random.choice([True, False]):
            headers["DNT"] = "1"
            
        return headers

    def get_season_id_mapping(self) -> Dict[str, int]:
        """Get season name to SofaScore season ID mapping with validation"""
        try:
            # Import here to avoid circular import
            from .core_constants import SofascoreConstants
            season_ids = SofascoreConstants.SEASON_IDS.copy()
            
            # Validate that all season IDs are integers
            validated_ids = {}
            for season_name, season_id in season_ids.items():
                if isinstance(season_id, int) and season_id > 0:
                    validated_ids[season_name] = season_id
                else:
                    logging.warning(f"Invalid season ID for {season_name}: {season_id}")
                    
            return validated_ids
            
        except ImportError as e:
            logging.error(f"Cannot import SofascoreConstants: {e}")
            # Fallback với default season IDs
            return {
                "2017/18": 13380,
                "2018/19": 17359,
                "2019/20": 23776,
                "2020/21": 29415,
                "2021/22": 37036,
                "2022/23": 41886,
                "2023/24": 52186,
                "2024/25": 61627
            }
        except Exception as e:
            logging.error(f"Error getting season ID mapping: {e}")
            return {}

    def get_target_seasons_with_ids(self, seasons: 'SeasonSettings') -> List[Tuple[int, str, int]]:
        """
        Get target seasons with their SofaScore IDs
        Returns: List of (year, season_name, sofascore_id)
        """
        target_seasons = seasons.get_target_seasons()  # List[Tuple[int, str]]
        sofascore_ids = self.get_season_id_mapping()  # Dict[str, int]
        
        result = []
        for year, season_name in target_seasons:
            sofascore_id = sofascore_ids.get(season_name)
            if sofascore_id:
                result.append((year, season_name, sofascore_id))
            else:
                logging.warning(f"No SofaScore ID found for season {season_name}")
                
        return result

    def validate_season_consistency(self, seasons: 'SeasonSettings') -> bool:
        """Validate rằng supported_seasons khớp với SofaScore season IDs"""
        try:
            sofascore_mapping = self.get_season_id_mapping()  # Dict[str, int]
            sofascore_seasons = set(sofascore_mapping.keys())  # Set of season names
            supported_seasons = set(seasons.supported_seasons.values())  # Set of season names
            
            # Check if all config seasons have corresponding SofaScore IDs
            missing_in_sofascore = supported_seasons - sofascore_seasons
            if missing_in_sofascore:
                logging.warning(f"Seasons missing in SofaScore constants: {missing_in_sofascore}")
                return False
                
            # Check if all SofaScore seasons are supported
            missing_in_config = sofascore_seasons - supported_seasons
            if missing_in_config:
                logging.info(f"SofaScore seasons not configured: {missing_in_config}")
            
            return True
            
        except Exception as e:
            logging.error(f"Error validating season consistency: {e}")
            return False

    @property 
    def is_configured(self) -> bool:
        """Kiểm tra Sofascore có được cấu hình đầy đủ không"""
        basic_config = bool(
            self.base_url and 
            self.premier_league_id and 
            self.user_agents and
            self.requests_per_minute > 0
        )
        
        return basic_config

class ScrapingSettings(BaseSettings):
    """Cấu hình chung cho web scraping - Enhanced"""
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Timeout configuration - Tăng timeout cho scraping
    request_timeout: int = Field(default=45, env="SCRAPING_TIMEOUT", gt=0)
    connect_timeout: int = Field(default=15, env="SCRAPING_CONNECT_TIMEOUT", gt=0)
    read_timeout: int = Field(default=30, env="SCRAPING_READ_TIMEOUT", gt=0)
    
    # Retry configuration - Enhanced
    max_retries: int = Field(default=5, env="SCRAPING_MAX_RETRIES", ge=1)
    retry_delay: float = Field(default=2.0, env="SCRAPING_RETRY_DELAY", ge=0.5)
    backoff_factor: float = Field(default=2.5, env="SCRAPING_BACKOFF_FACTOR", ge=1.0)
    
    # Rate limiting - Stricter for scraping
    delay_between_requests: float = Field(default=2.0, env="SCRAPING_DELAY", ge=0.5)
    random_delay_range: Tuple[float, float] = Field(default=(1.0, 3.0), env="SCRAPING_RANDOM_DELAY")
    concurrent_requests: int = Field(default=3, env="SCRAPING_CONCURRENT", ge=1, le=10)  # Giảm concurrent
    
    # Browser simulation - Enhanced
    enable_javascript: bool = Field(default=False, env="SCRAPING_ENABLE_JS")
    headless: bool = Field(default=True, env="SCRAPING_HEADLESS")
    browser_type: str = Field(default="chrome", env="SCRAPING_BROWSER")  # chrome, firefox, safari
    
    # Proxy configuration
    proxy_urls: List[str] = Field(default_factory=list, env="SCRAPING_PROXIES")
    rotate_proxies: bool = Field(default=False, env="SCRAPING_ROTATE_PROXIES")
    proxy_rotation_interval: int = Field(default=50, env="SCRAPING_PROXY_ROTATION", gt=0)
    
    # Cache configuration - Enhanced
    enable_cache: bool = Field(default=True, env="SCRAPING_ENABLE_CACHE")
    cache_ttl: int = Field(default=7200, env="SCRAPING_CACHE_TTL", gt=0)  # 2 hours
    cache_dir: str = Field(default="cache/scraping", env="SCRAPING_CACHE_DIR")
    
    # Error handling - Enhanced
    ignore_ssl_errors: bool = Field(default=False, env="SCRAPING_IGNORE_SSL")
    ignore_robots_txt: bool = Field(default=True, env="SCRAPING_IGNORE_ROBOTS")  # For API scraping
    max_redirects: int = Field(default=5, env="SCRAPING_MAX_REDIRECTS", ge=0, le=10)
    
    # Data quality settings
    validate_json_response: bool = Field(default=True, env="SCRAPING_VALIDATE_JSON")
    min_response_size: int = Field(default=10, env="SCRAPING_MIN_RESPONSE_SIZE", ge=0)
    max_response_size: int = Field(default=10485760, env="SCRAPING_MAX_RESPONSE_SIZE", gt=0)  # 10MB
    
    # Monitoring and logging
    enable_metrics: bool = Field(default=True, env="SCRAPING_ENABLE_METRICS")
    log_failed_requests: bool = Field(default=True, env="SCRAPING_LOG_FAILURES")
    save_failed_responses: bool = Field(default=False, env="SCRAPING_SAVE_FAILURES")
    
    # Giả lập trình duyệt
    browser_impersonate: str = Field(default="chrome110", env="SCRAPING_BROWSER_IMPERSONATE")

    @field_validator("proxy_urls", mode="before")
    @classmethod
    def parse_proxy_urls(cls, value) -> List[str]:
        """Parse proxy URLs từ string hoặc list"""
        if not value:
            return []
        
        if isinstance(value, str):
            proxies = []
            for separator in [",", ";", "\n"]:
                if separator in value:
                    proxies = [p.strip() for p in value.split(separator) if p.strip()]
                    break
            else:
                proxies = [value.strip()] if value.strip() else []
            return proxies
        
        if isinstance(value, list):
            return [str(proxy).strip() for proxy in value if str(proxy).strip()]
        
        return []

    @field_validator("random_delay_range", mode="before")
    @classmethod
    def parse_delay_range(cls, value) -> Tuple[float, float]:
        """Parse delay range từ string hoặc tuple"""
        if isinstance(value, str):
            try:
                if "," in value:
                    parts = value.split(",")
                    return (float(parts[0].strip()), float(parts[1].strip()))
                elif "-" in value:
                    parts = value.split("-")
                    return (float(parts[0].strip()), float(parts[1].strip()))
            except (ValueError, IndexError):
                pass
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            return (float(value[0]), float(value[1]))
        
        return (1.0, 3.0)  # Default

    @field_validator("browser_type")
    @classmethod
    def validate_browser_type(cls, v: str) -> str:
        """Validate browser type"""
        allowed_browsers = ["chrome", "firefox", "safari"]
        if v.lower() not in allowed_browsers:
            raise ValueError(f"Browser type must be one of: {allowed_browsers}")
        return v.lower()
    
    @field_validator("cache_dir")
    @classmethod
    def validate_cache_dir(cls, v: str) -> str:
        """Ensure cache directory path is valid"""
        if not v or v.isspace():
            raise ValueError("Cache directory cannot be empty")
        return v.strip()    
    
    def get_random_delay(self) -> float:
        """Tạo delay ngẫu nhiên trong khoảng cho phép"""
        min_delay, max_delay = self.random_delay_range
        return random.uniform(min_delay, max_delay)

    def get_random_proxy(self) -> Optional[str]:
        """Lấy ngẫu nhiên một proxy (nếu có)"""
        if not self.proxy_urls or not self.rotate_proxies:
            return None
        return random.choice(self.proxy_urls)

    @property
    def is_configured(self) -> bool:
        """Kiểm tra scraping config có hợp lệ không"""
        return (
            self.request_timeout > 0 and 
            self.max_retries >= 1 and 
            self.concurrent_requests >= 1 and
            self.random_delay_range[0] < self.random_delay_range[1]
        )

class SeasonSettings(BaseSettings):
    """Cấu hình seasons với timezone-aware logic"""
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Updated để bao gồm 7 seasons gần nhất
    raw_supported_seasons: str = Field(
        default="2017:2017/18,2018:2018/19,2019:2019/20,2020:2020/21,2021:2021/22,2022:2022/23,2023:2023/24,2024:2024/25",
        env="SUPPORTED_SEASONS"
    )
    timezone: str = Field(default="Europe/London", env="SEASON_TIMEZONE")
    seasons_to_fetch: int = Field(
        default=7, env="SEASONS_TO_FETCH", ge=1, le=15,
        description="Số lượng mùa giải gần nhất (đã hoàn thành) để lấy dữ liệu."
    )    
    
    @property
    def supported_seasons(self) -> Dict[int, str]:
        try:
            result = {}
            pairs = self.raw_supported_seasons.split(",")
            for pair in pairs:
                if ":" not in pair:
                    continue
                k, v = pair.split(":", 1)
                result[int(k.strip())] = v.strip()
            return result
        except Exception:
            return self._get_default_seasons()

    @classmethod
    def _get_default_seasons(cls) -> Dict[int, str]:
        """Get default seasons mapping - 7 seasons gần nhất"""
        return {
            2017: "2017/18", 2018: "2018/19", 2019: "2019/20",
            2020: "2020/21", 2021: "2021/22", 2022: "2022/23", 
            2023: "2023/24", 2024: "2024/25"
        }

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone string"""
        try:
            pytz.timezone(v)
            return v
        except pytz.exceptions.UnknownTimeZoneError:
            logging.warning(f"Unknown timezone '{v}', using 'Europe/London'")
            return "Europe/London"

    @property
    def latest_season(self) -> int:
        """Lấy season mới nhất có sẵn (không vượt quá năm hiện tại)"""
        try:
            tz = pytz.timezone(self.timezone)
            current_year = datetime.now(tz).year
            valid_seasons = [y for y in self.supported_seasons.keys() if y <= current_year]
            return max(valid_seasons) if valid_seasons else max(self.supported_seasons.keys())
        except Exception:
            return max(self.supported_seasons.keys())

    @property
    def current_season_year_start(self) -> int:
        """Xác định năm bắt đầu của mùa giải hiện tại (ví dụ: 2023 cho mùa 2023/24)."""
        try:
            tz = pytz.timezone(self.timezone)
            now = datetime.now(tz)
            # Mùa giải mới bắt đầu từ tháng 8
            return now.year if now.month >= 8 else now.year - 1
        except Exception:
            # Fallback an toàn
            now = datetime.now(timezone.utc)
            return now.year if now.month >= 8 else now.year - 1

    def get_target_seasons(self) -> List[Tuple[int, str]]:
        """
        Lấy danh sách seasons target để scrape data (7 seasons gần nhất đã hoàn thành)
        """
        try:
            current_start_year = self.current_season_year_start
            
            completed_seasons = [
                (year, name) for year, name in self.supported_seasons.items()
                if year <= current_start_year
            ]
            
            # Sắp xếp giảm dần theo năm và lấy số lượng cần thiết
            completed_seasons.sort(key=lambda x: x[0], reverse=True)
            return completed_seasons[:self.seasons_to_fetch]
            
        except Exception as e:
            logging.error(f"Error getting target seasons: {e}. Using fallback.", exc_info=True)
            # Fallback: Lấy các mùa giải mặc định và cắt theo số lượng
            default_seasons = sorted(self._get_default_seasons().items(), key=lambda x: x[0], reverse=True)
            # Đảm bảo không bị IndexError
            
            now = datetime.now(timezone.utc)
            current_start_year = now.year if now.month >= 8 else now.year - 1            
            
            # Lọc các mùa đã hoàn thành và lấy số lượng cần thiết
            completed_seasons_fallback = [s for s in default_seasons if s[0] < current_start_year]
            return completed_seasons_fallback[:self.seasons_to_fetch]

    def get_season_id_from_year(self, year: int, sofascore_settings: 'SofascoreSettings') -> Optional[int]:
        """Get SofaScore season ID from year (e.g., 2023 -> season ID for 2023/24)"""
        season_name = self.supported_seasons.get(year)
        if not season_name:
            return None
            
        sofascore_mapping = sofascore_settings.get_season_id_mapping()
        return sofascore_mapping.get(season_name)

# ConfigManager đã được cập nhật để bỏ APIFootball
_config_instance: Optional['ConfigManager'] = None

class ConfigManager:
    """Quản lý cấu hình ứng dụng - Updated for SofaScore scraping"""
    
    def __init__(self):
        """Constructor - khởi tạo config cho SofaScore scraping"""
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self._load_config()
        self._initialized = True

    def _load_config(self):
        """Load và validate tất cả config sections."""
        try:
            self.db = DatabaseSettings()
            self.sofascore = SofascoreSettings()
            self.scraping = ScrapingSettings()
            self.seasons = SeasonSettings()
            
            self._validate_critical_config()
            
        except ValidationError as e:
            error_msg = f"Configuration validation failed: {e}"
            logging.critical(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e

    def _validate_critical_config(self):
        """Validate các config quan trọng cho scraping"""
        log = logging.getLogger(__name__)
        errors = []
        
        if not self.sofascore.is_configured:
            errors.append("Sofascore configuration is incomplete.")
        
        if not self.scraping.is_configured:
            errors.append("Scraping configuration is invalid.")
        
        if not self.db.is_configured:
            log.warning("Database not fully configured - ensure this is intentional for dev/test environment")
        
        if errors:
            raise RuntimeError(f"Critical configuration errors: {'; '.join(errors)}")

    def reload_config(self):
        """Nạp lại cấu hình"""
        log = logging.getLogger(__name__)
        log.info("Reloading configuration...")
        self._load_config()
        log.info("Configuration reloaded.")

    def get_season_id_from_year(self, year: int) -> Optional[int]:
        """Wrapper method để gọi SeasonSettings với SofascoreSettings"""
        return self.seasons.get_season_id_from_year(year, self.sofascore)
    
    def get_target_seasons_with_ids(self) -> List[Tuple[int, str, int]]:
        """Wrapper method để lấy target seasons với IDs"""
        return self.sofascore.get_target_seasons_with_ids(self.seasons)
    
    def validate_season_consistency(self) -> bool:
        """Wrapper method để validate season consistency"""
        return self.sofascore.validate_season_consistency(self.seasons)
    
    @property
    def is_production(self) -> bool:
        return os.getenv("ENVIRONMENT", "dev").lower() in ("production", "prod")

    @property
    def is_development(self) -> bool:
        return not self.is_production

def get_config() -> ConfigManager:
    """Hàm toàn cục để lấy instance cấu hình"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()        
    return _config_instance