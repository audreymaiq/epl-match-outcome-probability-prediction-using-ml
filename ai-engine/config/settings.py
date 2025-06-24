# ai-engine\config\settings.py

from pydantic import Field, AnyUrl, SecretStr, ValidationError
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Dict, Tuple, Optional
import os
import pytz
import logging
import urllib.parse
import random
import threading
from datetime import datetime


class DatabaseSettings(BaseSettings):
    """Cấu hình database với validation an toàn"""
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Bỏ qua các env vars không liên quan
    )
    
    host: str = Field(default="localhost", env="DB_HOST")
    port: int = Field(default=5432, env="DB_PORT", gt=0, le=65535)
    dbname: str = Field(default="premier_league", env="DB_NAME", min_length=1)
    user: str = Field(default="postgres", env="DB_USER", min_length=1)
    password: SecretStr = Field(default=SecretStr(""), env="DB_PASSWORD")

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
        pwd = self.password.get_secret_value()
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
            self.password.get_secret_value()
        )


class APIFootballSettings(BaseSettings):
    """Cấu hình API Football với multiple keys và rotation"""
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    base_url: AnyUrl = Field(
        default="https://v3.football.api-sports.io", 
        env="API_BASE_URL"
    )
    api_keys: List[SecretStr] = Field(
        default_factory=list, 
        env="API_FOOTBALL_KEY"
    )
    
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
    def parse_api_keys(cls, value) -> List[SecretStr]:
        """Xử lý nhiều định dạng API keys từ string hoặc list"""
        if not value:
            return []
            
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
            
            return [SecretStr(k) for k in keys if k]
            
        if isinstance(value, list):
            result = []
            for v in value:
                if isinstance(v, SecretStr):
                    result.append(v)
                elif v and str(v).strip():
                    result.append(SecretStr(str(v).strip()))
            return result
            
        return []

    def get_random_key(self) -> str:
        """Lấy ngẫu nhiên một API key với thread-safe rotation"""
        if not self.api_keys:
            raise ValueError("No API keys available - check API_FOOTBALL_KEY environment variable")
        
        key = random.choice(self.api_keys).get_secret_value()
        
        # Safe logging - chỉ log masked version
        if len(key) > 8:
            masked_key = f"{key[:4]}...{key[-4:]}"
        else:
            masked_key = f"{key[:2]}...{key[-2:]}" if len(key) > 4 else "***"
            
        # Only log if logging is configured
        try:
            logging.debug(f"Using API key: {masked_key}")
        except:
            pass  # Ignore logging errors
            
        return key

    @property
    def is_configured(self) -> bool:
        """Kiểm tra API có được cấu hình đầy đủ không"""
        return bool(self.base_url and self.api_keys)


class SeasonSettings(BaseSettings):
    """Cấu hình seasons với timezone-aware logic"""
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Default supported seasons
    supported_seasons: Dict[int, str] = Field(
        default_factory=lambda: {
            2016: "2016/17", 2017: "2017/18", 2018: "2018/19",
            2019: "2019/20", 2020: "2020/21", 2021: "2021/22", 
            2022: "2022/23", 2023: "2023/24", 2024: "2024/25"
        },
        env="SUPPORTED_SEASONS"
    )
    
    timezone: str = Field(default="Europe/London", env="SEASON_TIMEZONE")

    @field_validator("supported_seasons", mode="before")
    @classmethod
    def parse_seasons(cls, value) -> Dict[int, str]:
        """Parse season mapping từ string format hoặc dict"""
        if isinstance(value, dict):
            # Ensure keys are integers
            return {int(k): str(v) for k, v in value.items()}
            
        if isinstance(value, str) and value.strip():
            try:
                seasons: Dict[int, str] = {}
                pairs = value.split(",")
                for pair in pairs:
                    if not pair.strip() or ":" not in pair:
                        continue
                    k_str, v = pair.split(":", 1)
                    year = int(k_str.strip())
                    season = v.strip()
                    if year > 2000 and year < 2050:  # Sanity check
                        seasons[year] = season
                return seasons if seasons else cls._get_default_seasons()
            except (ValueError, TypeError) as e:
                # Log error but don't crash - use defaults
                try:
                    logging.warning(f"Invalid SUPPORTED_SEASONS format: '{value}' - {e}")
                except:
                    pass
                return cls._get_default_seasons()
        
        return cls._get_default_seasons()

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

    def get_seasons_to_fetch(self, start_year: int = 2018, min_count: int = 5) -> List[Tuple[int, int]]:
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


class ConfigManager:
    """Thread-safe singleton cho configuration management"""
    _instance: Optional['ConfigManager'] = None
    _lock = threading.RLock()  # Re-entrant lock để tránh deadlock

    def __new__(cls) -> 'ConfigManager':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Thread-safe initialization check
        with self._lock:
            if hasattr(self, '_initialized') and self._initialized:
                return
            
            self._initialized = False
            self._load_config()
            self._initialized = True

    def _load_config(self):
        """Load và validate tất cả config sections"""
        # Load environment nếu cần (tránh circular import)
        if not os.getenv("API_FOOTBALL_KEY"):
            try:
                # Import tại runtime để tránh circular dependency
                from config.env_loader import load_environment
                load_environment()
            except ImportError:
                # Nếu không có env_loader, skip
                pass

        try:
            self.db = DatabaseSettings()
            self.api = APIFootballSettings()
            self.seasons = SeasonSettings()
            
            # Validate critical config
            self._validate_critical_config()
            
        except ValidationError as e:
            error_msg = f"Configuration validation failed: {e}"
            try:
                logging.critical(error_msg)
            except:
                print(f"CRITICAL: {error_msg}")  # Fallback if logging not ready
            raise RuntimeError(error_msg) from e

    def _validate_critical_config(self):
        """Validate các config quan trọng"""
        errors = []
        
        # Validate API keys (bắt buộc)
        if not self.api.is_configured:
            errors.append("API Football keys are required but not configured")
        
        # Validate database (warning only cho dev)
        if not self.db.is_configured:
            try:
                logging.warning(
                    "Database not fully configured - ensure this is intentional for dev/test environment"
                )
            except:
                print("WARNING: Database not fully configured")
        
        if errors:
            raise RuntimeError(f"Critical configuration errors: {'; '.join(errors)}")

    def reload_config(self):
        """Reload configuration - useful for config updates"""
        with self._lock:
            self._initialized = False
            self._load_config()
            self._initialized = True

    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return os.getenv("ENVIRONMENT", "dev").lower() in ("production", "prod")

    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return os.getenv("ENVIRONMENT", "dev").lower() in ("development", "dev", "local")


# Global config instance - lazy initialization
def get_config() -> ConfigManager:
    """Get global config instance với thread-safe lazy loading"""
    return ConfigManager()


# Backward compatibility
config = get_config()