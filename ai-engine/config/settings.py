# ai-engine\config\settings.py

from pydantic import Field, AnyUrl, SecretStr, ValidationError
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Dict
import logging
import urllib.parse
import random
import threading

class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    host: str = Field(default="localhost", env="DB_HOST")
    port: int = Field(default=5432, env="DB_PORT")
    dbname: str = Field(default="premier_league", env="DB_NAME")
    user: str = Field(default="postgres", env="DB_USER")
    password: SecretStr = Field(default=SecretStr(""), env="DB_PASSWORD")

    @property
    def dsn(self) -> str:
        """Tạo connection string an toàn cho PostgreSQL, URL-encode mật khẩu."""
        pwd = self.password.get_secret_value()
        pwd_enc = urllib.parse.quote(pwd, safe="")
        return f"postgresql://{self.user}:{pwd_enc}@{self.host}:{self.port}/{self.dbname}"

class APIFootballSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    base_url: AnyUrl = Field(default="https://v3.football.api-sports.io", env="API_BASE_URL")
    api_keys: List[SecretStr] = Field(default_factory=list, env="API_FOOTBALL_KEY")

    @field_validator("base_url")
    @classmethod
    def validate_https(cls, value: AnyUrl) -> AnyUrl:
        """Đảm bảo chỉ sử dụng HTTPS."""
        if value.scheme != "https":
            raise ValueError("API base URL must use HTTPS")
        return value

    @field_validator("api_keys", mode="before")
    @classmethod
    def parse_api_keys(cls, value) -> List[SecretStr]:
        """Xử lý nhiều định dạng API keys từ string hoặc list."""
        if isinstance(value, str):
            return [SecretStr(k.strip()) for k in value.split(",") if k.strip()]
        if isinstance(value, list):
            result = []
            for v in value:
                if isinstance(v, SecretStr):
                    result.append(v)
                else:
                    result.append(SecretStr(str(v)))
            return result
        return []

    def get_random_key(self) -> str:
        """Lấy ngẫu nhiên một API key (masked logging nếu cần)."""
        if not self.api_keys:
            raise ValueError("No API keys available")
        key = random.choice(self.api_keys).get_secret_value()
        # Ví dụ: log masked 4 ký tự cuối, không log toàn bộ
        logging.debug(f"Using API key ending with: {key[-4:] if len(key) > 4 else key}")
        return key

class SeasonSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    supported_seasons: Dict[int, str] = Field(
        default_factory=lambda: {
            2016: "2016/17",
            2017: "2017/18",
            2018: "2018/19",
            2019: "2019/20",
            2020: "2020/21",
            2021: "2021/22",
            2022: "2022/23"
        },
        env="SUPPORTED_SEASONS"
    )

    @field_validator("supported_seasons", mode="before")
    @classmethod
    def parse_seasons(cls, value) -> Dict[int, str]:
        """Xử lý chuỗi mùa giải từ biến môi trường, fallback về default khi lỗi."""
        if isinstance(value, str):
            try:
                seasons = {}
                for pair in value.split(","):
                    pair = pair.strip()
                    if not pair or ":" not in pair:
                        continue
                    k_str, v = pair.split(":", 1)
                    seasons[int(k_str.strip())] = v.strip()
                return seasons
            except (ValueError, TypeError) as e:
                logging.error(f"Invalid SUPPORTED_SEASONS format: '{value}' - Error: {e}")
                # Trả về default rõ ràng
                return cls.model_fields["supported_seasons"].default_factory()
        # Nếu giá trị None hoặc đã là dict, Pydantic sẽ gán default hoặc giữ nguyên
        return value or cls.model_fields["supported_seasons"].default_factory()

    @property
    def latest_season(self) -> int:
        """Lấy mùa giải mới nhất; fallback 2022 nếu không có."""
        seasons = self.supported_seasons or {}
        try:
            return max(seasons.keys())
        except ValueError:
            logging.warning("Using fallback season 2022")
            return 2022

class ConfigManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        try:
            # Đảm bảo logging đã được cấu hình trước khi khởi tạo, nếu bạn dùng logging_config
            self.db = DatabaseSettings()
            self.api = APIFootballSettings()
            self.seasons = SeasonSettings()
            self.validate_config()
            self._initialized = True
        except ValidationError as e:
            logging.critical(f"Configuration validation error: {e}")
            raise

    def validate_config(self):
        if not self.db.password.get_secret_value():
            logging.warning("Database password is empty - ensure for local/dev only")
        if not self.api.api_keys:
            logging.critical("API keys are required for Football API access")
            raise RuntimeError("Missing API keys for Football API")

# Khởi tạo toàn cục
config = ConfigManager()
