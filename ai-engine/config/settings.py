# ai-engine\config\settings.py

from pydantic import Field, AnyUrl, ValidationError
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import os
import pytz
import logging
import urllib.parse
import random
from datetime import datetime

ENV_FILE_PATH = Path(__file__).parent.parent / ".env"

print("="*50)
print(f"DEBUG: Searching for .env file at: {ENV_FILE_PATH}")
if ENV_FILE_PATH.exists():
    print("DEBUG: .env file FOUND!")
else:
    print("DEBUG: .env file NOT FOUND at this path!")
print("="*50)

class DatabaseSettings(BaseSettings):
    """Cấu hình database với validation an toàn"""
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Bỏ qua các env vars không liên quan
    )
    
    host: str = Field(default="localhost", env="DB_HOST")
    port: int = Field(default=5432, env="DB_PORT", gt=0, le=65535)
    dbname: str = Field(default="premier_league", env="DB_NAME", min_length=1)
    user: str = Field(default="postgres", env="DB_USER", min_length=1)
    password: str = Field(default="", env="DB_PASSWORD")  # Changed from SecretStr to str

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
        pwd = self.password  # No longer need get_secret_value()
        # URL encode tất cả special characters
        user_enc = urllib.parse.quote(self.user, safe="")
        pwd_enc = urllib.parse.quote(pwd, safe="")
        host_enc = urllib.parse.quote(self.host, safe="")
        db_enc = urllib.parse.quote(self.dbname, safe="")
        
        return f"postgresql://{user_enc}:{pwd_enc}@{host_enc}:{self.port}/{db_enc}"

    @property
    def is_configured(self) -> bool:
        """Kiểm tra database có được cấu hình đầy đủ không"""
        return bool(
            self.host and 
            self.user and 
            self.dbname and
            self.password  # No longer need get_secret_value()
        )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        print(f"[DEBUG] Loaded DB_USER: {self.user}")
        print(f"[DEBUG] Loaded DB_PASSWORD: {self.password}")


class APIFootballSettings(BaseSettings):
    """Cấu hình API Football với multiple keys và rotation (legacy support)"""
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
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

    def __init__(self, **values):
        super().__init__(**values)
        if not self.api_keys:
            raw = os.getenv("API_FOOTBALL_KEY")
            if raw:
                self.api_keys = [(k.strip()) for k in raw.split(",") if k.strip()]
        # print("DEBUG __init__ API_FOOTBALL_KEY:", os.getenv("API_FOOTBALL_KEY"))
        # print("DEBUG self.api_keys:", self.api_keys)


class SofascoreSettings(BaseSettings):
    """Cấu hình Sofascore API không chính thức"""
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    base_url: AnyUrl = Field(
        default="https://api.sofascore.com/api/v1", 
        env="SOFASCORE_BASE_URL"
    )
    
    # Premier League tournament ID trên Sofascore
    premier_league_id: int = Field(default=17, env="SOFASCORE_EPL_ID")
    
    # Rate limiting để tránh bị block
    requests_per_minute: int = Field(default=60, env="SOFASCORE_RATE_LIMIT", gt=0)
    delay_between_requests: float = Field(default=1.0, env="SOFASCORE_DELAY", ge=0.1)
    
    # Retry configuration
    max_retries: int = Field(default=3, env="SOFASCORE_MAX_RETRIES", ge=1)
    retry_delay: float = Field(default=2.0, env="SOFASCORE_RETRY_DELAY", ge=0.5)
    
    # Headers rotation để tránh detection
    user_agents: List[str] = Field(
        default_factory=lambda: [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ],
        env="SOFASCORE_USER_AGENTS"
    )

    @field_validator("base_url")
    @classmethod
    def validate_https(cls, value: AnyUrl) -> AnyUrl:
        """Đảm bảo chỉ sử dụng HTTPS cho bảo mật"""
        if not value or str(value).strip() == "":
            raise ValueError("Sofascore base URL cannot be empty")
        if value.scheme != "https":
            raise ValueError("Sofascore base URL must use HTTPS for security")
        return value

    @field_validator("user_agents", mode="before")
    @classmethod
    def parse_user_agents(cls, value) -> List[str]:
        """Parse user agents từ string hoặc list"""
        if not value:
            return cls.model_fields['user_agents'].default_factory()
        
        if isinstance(value, str):
            # Split by semicolon hoặc newline
            agents = []
            for separator in [";", "\n"]:
                if separator in value:
                    agents = [ua.strip() for ua in value.split(separator) if ua.strip()]
                    break
            else:
                agents = [value.strip()] if value.strip() else []
            return agents if agents else cls.model_fields['user_agents'].default_factory()
        
        if isinstance(value, list):
            return [str(ua).strip() for ua in value if str(ua).strip()]
        
        return cls.model_fields['user_agents'].default_factory()

    def get_random_user_agent(self) -> str:
        """Lấy ngẫu nhiên một User-Agent"""
        return random.choice(self.user_agents)

    def get_headers(self) -> Dict[str, str]:
        """Tạo headers cho request"""
        return {
            "User-Agent": self.get_random_user_agent(),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site"
        }

    @property
    def is_configured(self) -> bool:
        """Kiểm tra Sofascore có được cấu hình đầy đủ không"""
        return bool(self.base_url and self.premier_league_id)


class ScrapingSettings(BaseSettings):
    """Cấu hình chung cho web scraping"""
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Timeout configuration
    request_timeout: int = Field(default=30, env="SCRAPING_TIMEOUT", gt=0)
    connect_timeout: int = Field(default=10, env="SCRAPING_CONNECT_TIMEOUT", gt=0)
    
    # Retry configuration
    max_retries: int = Field(default=3, env="SCRAPING_MAX_RETRIES", ge=1)
    retry_delay: float = Field(default=1.0, env="SCRAPING_RETRY_DELAY", ge=0.1)
    backoff_factor: float = Field(default=2.0, env="SCRAPING_BACKOFF_FACTOR", ge=1.0)
    
    # Rate limiting
    delay_between_requests: float = Field(default=1.0, env="SCRAPING_DELAY", ge=0.1)
    concurrent_requests: int = Field(default=5, env="SCRAPING_CONCURRENT", ge=1, le=20)
    
    # Browser simulation
    enable_javascript: bool = Field(default=False, env="SCRAPING_ENABLE_JS")
    headless: bool = Field(default=True, env="SCRAPING_HEADLESS")
    
    # Proxy configuration (optional)
    proxy_urls: List[str] = Field(default_factory=list, env="SCRAPING_PROXIES")
    rotate_proxies: bool = Field(default=False, env="SCRAPING_ROTATE_PROXIES")
    
    # Cache configuration
    enable_cache: bool = Field(default=True, env="SCRAPING_ENABLE_CACHE")
    cache_ttl: int = Field(default=3600, env="SCRAPING_CACHE_TTL", gt=0)  # 1 hour
    
    # Error handling
    ignore_ssl_errors: bool = Field(default=False, env="SCRAPING_IGNORE_SSL")
    
    @field_validator("proxy_urls", mode="before")
    @classmethod
    def parse_proxy_urls(cls, value) -> List[str]:
        """Parse proxy URLs từ string hoặc list"""
        if not value:
            return []
        
        if isinstance(value, str):
            # Split by comma hoặc semicolon
            proxies = []
            for separator in [",", ";"]:
                if separator in value:
                    proxies = [p.strip() for p in value.split(separator) if p.strip()]
                    break
            else:
                proxies = [value.strip()] if value.strip() else []
            return proxies
        
        if isinstance(value, list):
            return [str(proxy).strip() for proxy in value if str(proxy).strip()]
        
        return []

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
            self.concurrent_requests >= 1
        )


class SeasonSettings(BaseSettings):
    """Cấu hình seasons với timezone-aware logic"""
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    raw_supported_seasons: str = Field(
        default="2016:2016/17,2017:2017/18,2018:2018/19,2019:2019/20,2020:2020/21,2021:2021/22,2022:2022/23,2023:2023/24",
        env="SUPPORTED_SEASONS"
    )
    timezone: str = Field(default="Europe/London", env="SEASON_TIMEZONE")

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
        """Get default seasons mapping"""
        return {
            2016: "2016/17", 2017: "2017/18", 2018: "2018/19",
            2019: "2019/20", 2020: "2020/21", 2021: "2021/22", 
            2022: "2022/23", 2023: "2023/24", 2024: "2024/25"
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
    def current_season(self) -> Tuple[int, int]:
        """Xác định season hiện tại dựa trên thời gian (Aug-July cycle)"""
        try:
            tz = pytz.timezone(self.timezone)
            now = datetime.now(tz)
            year = now.year
            
            # Premier League season chạy từ tháng 8 năm X đến tháng 5 năm X+1
            if now.month >= 8:  # Tháng 8-12
                return (year, year + 1)
            else:  # Tháng 1-7
                return (year - 1, year)
        except Exception:
            # Fallback to simple logic
            year = datetime.now().year
            return (year, year + 1) if datetime.now().month >= 8 else (year - 1, year)

    @property
    def last_completed_season(self) -> Tuple[int, int]:
        """Season đã hoàn thành gần nhất"""
        start, end = self.current_season
        return (start - 1, end - 1)

    def get_seasons_to_fetch(self, start_year: int = 2016, min_count: int = 5) -> List[Tuple[int, int]]:
        """
        Lấy danh sách seasons cần fetch data
        Fixed: Không thể dùng @property với parameters
        """
        try:
            current_start, current_end = self.current_season
            
            # Generate seasons từ start_year đến current season (exclusive)
            seasons = []
            for year in range(start_year, current_start):
                seasons.append((year, year + 1))
            
            # Đảm bảo có ít nhất min_count seasons
            if len(seasons) < min_count:
                extra_needed = min_count - len(seasons)
                for i in range(1, extra_needed + 1):
                    year = start_year - i
                    if year > 2000:  # Sanity check
                        seasons.insert(0, (year, year + 1))
            
            return seasons
        except Exception:
            # Fallback to basic logic
            current_year = datetime.now().year
            return [(y, y + 1) for y in range(max(2016, start_year), current_year)]


# Biến toàn cục (private) để lưu trữ instance duy nhất. Nó sẽ được khởi tạo TRỄ (lazy).
_config_instance: Optional['ConfigManager'] = None

class ConfigManager:
    """
    Quản lý cấu hình ứng dụng.
    Được khởi tạo một lần duy nhất thông qua hàm get_config().
    """
    # Không cần __new__ hay lock ở đây nữa, vì hàm get_config sẽ xử lý việc đó.
    
    def __init__(self):
        """
        Constructor này chỉ nên được gọi MỘT LẦN DUY NHẤT bởi get_config().
        Nó sẽ nạp và xác thực toàn bộ cấu hình.
        """
        # Thêm một log để biết chính xác khi nào nó được tạo
        log = logging.getLogger(__name__)
        log.info(">>>>>> Initializing a new ConfigManager instance... <<<<<<")
        
        # Biến này để đảm bảo __init__ không bị gọi lại trên cùng một đối tượng
        # (mặc dù với cấu trúc mới, điều này khó xảy ra)
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self._load_config()
        self._initialized = True
        log.info(">>>>>> ConfigManager instance initialized successfully. <<<<<<")

    def _load_config(self):
        """Load và validate tất cả config sections."""
        try:
            # Pydantic-settings sẽ tự động đọc từ các biến môi trường đã được nạp
            self.db = DatabaseSettings()
            self.api = APIFootballSettings()
            self.sofascore = SofascoreSettings()
            self.scraping = ScrapingSettings()
            self.seasons = SeasonSettings()
            
            self._validate_critical_config()
            
        except ValidationError as e:
            error_msg = f"Configuration validation failed: {e}"
            logging.critical(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e

    def _validate_critical_config(self):
        """Validate các config quan trọng."""
        log = logging.getLogger(__name__)
        errors = []
        
        if not self.sofascore.is_configured:
            errors.append("Sofascore configuration is incomplete.")
        
        if not self.scraping.is_configured:
            errors.append("Scraping configuration is invalid.")
        
        if not self.api.is_configured:
            log.warning("API-Football is not configured - skipping API calls")
        
        if not self.db.is_configured:
            # Đây chỉ là cảnh báo, không phải lỗi nghiêm trọng
            log.warning("Database not fully configured - ensure this is intentional for dev/test environment")
        
        if errors:
            raise RuntimeError(f"Critical configuration errors: {'; '.join(errors)}")

    def reload_config(self):
        """Nạp lại cấu hình. Hữu ích cho các kịch bản test hoặc cập nhật nóng."""
        log = logging.getLogger(__name__)
        log.info("Reloading configuration...")
        self._load_config()
        log.info("Configuration reloaded.")

    @property
    def is_production(self) -> bool:
        return os.getenv("ENVIRONMENT", "dev").lower() in ("production", "prod")

    @property
    def is_development(self) -> bool:
        return not self.is_production

def get_config() -> ConfigManager:
    """
    Hàm toàn cục để lấy instance cấu hình.
    Đây là cổng vào DUY NHẤT và đảm bảo khởi tạo trễ (lazy initialization).
    """
    global _config_instance
    
    # Chỉ khi instance chưa tồn tại, chúng ta mới tạo mới nó.
    if _config_instance is None:
        # Dòng này sẽ chỉ chạy một lần trong suốt vòng đời của ứng dụng.
        _config_instance = ConfigManager()
        
    return _config_instance