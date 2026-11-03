# backend\config\settings.py

from pydantic import AliasChoices, Field, AnyUrl, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Dict, Optional
from pathlib import Path
import os
import logging
import urllib.parse
import random

ENV_FILE_PATH = (Path(__file__).parent.parent / ".env").resolve()
    
class DatabaseSettings(BaseSettings):
    """Cấu hình database với validation an toàn"""
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    host: str = Field(default="localhost", validation_alias=AliasChoices("DB_HOST", "HOST"))
    port: int = Field(default=5432, gt=0, le=65535, validation_alias=AliasChoices("DB_PORT", "PORT"))
    dbname: str = Field(default="premier_league", min_length=1, validation_alias=AliasChoices("DB_NAME", "DBNAME"))
    user: str = Field(default="postgres", min_length=1, validation_alias=AliasChoices("DB_USER", "USER"))
    password: str = Field(default="", validation_alias=AliasChoices("DB_PASSWORD", "PASSWORD"))

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
        
        return f"postgresql+psycopg2://{user_enc}:{pwd_enc}@{host_enc}:{self.port}/{db_enc}"

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
        validation_alias="API_FOOTBALL_BASE_URL"
    )
    api_keys: List[str] = Field(
        default_factory=list, 
        validation_alias="API_FOOTBALL_KEY"
    )  # Changed from List[SecretStr] to List[str]
    
    # Rate limiting config
    requests_per_minute: int = Field(default=100, validation_alias="API_RATE_LIMIT", gt=0)
    
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
        validation_alias="SOFASCORE_BASE_URL"
    )
    
    # Web URLs cho scraping fallback
    web_base_url: AnyUrl = Field(
        default="https://www.sofascore.com",
        validation_alias="SOFASCORE_WEB_URL"
    )
    
    # Premier League tournament ID trên Sofascore
    premier_league_id: int = Field(default=17, validation_alias="SOFASCORE_EPL_ID")
    
    # Rate limiting để tránh bị block
    requests_per_minute: int = Field(default=30, validation_alias="SOFASCORE_RATE_LIMIT", gt=0)  # Giảm xuống để an toàn
    delay_between_requests: float = Field(default=2.0, validation_alias="SOFASCORE_DELAY", ge=0.5)  # Tăng delay
    
    # Retry configuration - Enhanced
    max_retries: int = Field(default=5, validation_alias="SOFASCORE_MAX_RETRIES", ge=1)  # Tăng retries
    retry_delay: float = Field(default=3.0, validation_alias="SOFASCORE_RETRY_DELAY", ge=1.0)  # Tăng delay
    exponential_backoff: bool = Field(default=True, validation_alias="SOFASCORE_EXPONENTIAL_BACKOFF")
    
    # Circuit breaker để tránh spam requests
    circuit_breaker_threshold: int = Field(default=5, validation_alias="SOFASCORE_CIRCUIT_THRESHOLD", ge=3)
    circuit_breaker_timeout: int = Field(default=300, validation_alias="SOFASCORE_CIRCUIT_TIMEOUT", ge=60)  # 5 minutes
    
    # Headers rotation để tránh detection - Enhanced
    user_agents: List[str] = Field(
        default_factory=lambda: [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0"
        ],
        validation_alias="SOFASCORE_USER_AGENTS",
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
        validation_alias="SOFASCORE_ACCEPT_LANGUAGES",
        description="Danh sách Accept-Language để xoay vòng, phân tách bằng dấu ; hoặc newline."
    )
    
    # Session management
    session_rotation_interval: int = Field(default=100, validation_alias="SOFASCORE_SESSION_ROTATION", gt=0)  # Rotate session sau N requests
    enable_cookies: bool = Field(default=True, validation_alias="SOFASCORE_ENABLE_COOKIES")
    
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

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.web_base_url and self.premier_league_id > 0)


class ScrapingSettings(BaseSettings):
    """Network and pacing options shared by data providers."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH), env_file_encoding="utf-8", extra="ignore"
    )

    connect_timeout: int = Field(default=15, validation_alias="SCRAPING_CONNECT_TIMEOUT", gt=0)
    read_timeout: int = Field(default=30, validation_alias="SCRAPING_READ_TIMEOUT", gt=0)
    max_retries: int = Field(default=5, validation_alias="SCRAPING_MAX_RETRIES", ge=1)
    backoff_factor: float = Field(default=2.5, validation_alias="SCRAPING_BACKOFF_FACTOR", ge=1)
    browser_impersonate: str = Field(default="chrome110", validation_alias="SCRAPING_BROWSER_IMPERSONATE")
    ignore_ssl_errors: bool = Field(default=False, validation_alias="SCRAPING_IGNORE_SSL")
    min_delay: float = Field(default=1.0, validation_alias="SCRAPING_MIN_DELAY", ge=0)
    max_delay: float = Field(default=3.0, validation_alias="SCRAPING_MAX_DELAY", gt=0)

    @property
    def is_configured(self) -> bool:
        return self.min_delay < self.max_delay

    def get_random_delay(self) -> float:
        return random.uniform(self.min_delay, self.max_delay)

class SeasonSettings(BaseSettings):
    """Number of recent EPL seasons to ingest."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH), env_file_encoding="utf-8", extra="ignore"
    )
    seasons_to_fetch: int = Field(
        default=7, validation_alias="SEASONS_TO_FETCH", ge=1, le=15
    )


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
            self._sofascore = None
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

    @property
    def sofascore(self) -> SofascoreSettings:
        if self._sofascore is None:
            self._sofascore = SofascoreSettings()
        return self._sofascore

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
