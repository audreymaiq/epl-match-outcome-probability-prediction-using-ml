# ai-engine\elt_pipeline\extract\api_football_client.py

import logging
import time
import requests
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log, retry_if_exception
from typing import Any, Dict, List, Optional, Tuple

# Import module endpoint: giả sử cùng package, hoặc điều chỉnh path nếu khác
from .api_endpoints import APIFootballEndpoints, build_url, get_rate_limit, APIFootballConfig

# Config của bạn (giả sử config.settings.config.API chứa KEYS, TIMEOUT, USE_RAPIDAPI tùy bạn set)
from config.settings import config

logger = logging.getLogger(__name__)

class APIFootballClient:
    """Client toàn diện cho API-Football với quản lý endpoint, rate limit và xoay key."""

    def __init__(self):
        # config.API.KEYS: List[str] các API key (direct API-Football key hoặc RapidAPI key tuỳ USE_RAPIDAPI)
        self.api_keys: List[str] = getattr(config.API, "KEYS", []) or []
        if not self.api_keys:
            logger.warning("No API keys provided in config.API.KEYS. Các request sẽ dùng key rỗng.")
        # Timeout cho requests, ví dụ config.API.TIMEOUT = số giây
        self.timeout = getattr(config.API, "TIMEOUT", None)
        # Session với retry cơ bản cho HTTP status
        self._session = self._create_session()
        # Xoay key
        self._key_rotator = self.KeyRotator(self.api_keys)
        # Lock để thread-safe xoay key
        self._lock = threading.Lock()

    class KeyRotator:
        """Quản lý xoay vòng API key thông minh"""
        def __init__(self, keys: List[str]):
            self.keys = keys or []
            self.index = 0
            self.last_failed: Dict[str, float] = {}
            self.cooldown = 300  # 5 phút cooldown

        def get_current_key(self) -> Optional[str]:
            return self.keys[self.index] if self.keys else None

        def next_key(self):
            if not self.keys:
                return
            self.index = (self.index + 1) % len(self.keys)

        def report_failure(self, key: str):
            if not key:
                return
            self.last_failed[key] = time.time()
            # Sau khi đánh dấu failure, chuyển sang key tiếp
            self.next_key()

        def is_key_ready(self, key: str) -> bool:
            if not key:
                return False
            last = self.last_failed.get(key, 0)
            return (time.time() - last) > self.cooldown

        def all_keys_failed(self) -> bool:
            if not self.keys:
                return True
            # Nếu mọi key đều trong cooldown, trả về True
            return all(not self.is_key_ready(k) for k in self.keys)

    def _create_session(self) -> requests.Session:
        """
        Tạo session với retry policy cơ bản (chỉ cho status nhất định, GET).
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]  # bạn chỉ cần GET, nhưng có thể mở rộng
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=100
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    @staticmethod
    def _should_retry(e: Exception) -> bool:
        """
        Logic để tenacity quyết định có retry hay không:
        Retry nếu HTTPError với status thuộc danh sách, hoặc ConnectionError/Timeout.
        """
        if isinstance(e, requests.HTTPError):
            status = e.response.status_code if e.response is not None else None
            return status in [429, 401, 403, 500, 502, 503, 504]
        return isinstance(e, (requests.ConnectionError, requests.Timeout))

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(lambda exc: APIFootballClient._should_retry(exc)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def call_api(
        self,
        endpoint_key: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        page: int = None,
        per_page: int = 100
    ) -> Tuple[List[Dict], Dict]:
        """
        Gọi API-Football:
        - endpoint_key: string tên Enum member, ví dụ "LEAGUES", "FIXTURES", v.v. (case-insensitive)
        - params: dict tham số query
        - method: HTTP method, mặc định "GET"
        - page, per_page: nếu cần pagination
        Trả về (data_list, metadata_dict).
        """
        # Chuẩn bị params
        params = params.copy() if params else {}
        if page is not None:
            params.update({"page": page, "per_page": per_page})

        # Chuyển endpoint_key sang Enum
        try:
            endpoint_enum = APIFootballEndpoints.from_string(endpoint_key)
        except ValueError as e:
            logger.error(f"Endpoint error: {e}")
            raise

        # Rate limit động theo endpoint
        try:
            rate_limit = get_rate_limit(endpoint_enum)
            # Sleep để tuân thủ requests/giây
            time.sleep(1.0 / rate_limit)
        except Exception as e:
            # Nếu có ZeroDivisionError hoặc lỗi khác, fallback sleep ngắn
            logger.warning(f"Rate limit calculation error: {e}. Sử dụng delay fallback 0.1s.")
            time.sleep(0.1)

        # Xoay key trong lock
        with self._lock:
            current_key = self._key_rotator.get_current_key()
            # Kiểm tra cooldown key hiện tại
            if current_key and not self._key_rotator.is_key_ready(current_key):
                self._key_rotator.next_key()
                current_key = self._key_rotator.get_current_key()

            # Nếu mọi key đều failed
            if self._key_rotator.all_keys_failed():
                logger.critical("All API keys are in cooldown or không có key. Service unavailable.")
                raise RuntimeError("All API keys exhausted or not provided.")

        # Xây dựng URL
        try:
            url = build_url(endpoint_enum, params)
        except Exception as e:
            logger.error(f"Build URL failed for endpoint {endpoint_enum}: {e}")
            raise

        # Chuẩn bị header:
        # Kiểm tra config xem dùng RapidAPI hay direct API
        use_rapidapi = getattr(config.API, "USE_RAPIDAPI", False)
        headers: Dict[str, str] = {"Accept-Encoding": "gzip"}
        if use_rapidapi:
            # current_key ở đây phải là RapidAPI key
            headers["x-rapidapi-key"] = current_key or ""
            # Host: domain không có https://
            # Lấy host từ BASE_URL, ví dụ "v3.football.api-sports.io"
            host = APIFootballConfig.BASE_URL.replace("https://", "").replace("http://", "").strip("/")
            headers["x-rapidapi-host"] = host
        else:
            # direct API-Football: dùng x-apisports-key
            headers["x-apisports-key"] = current_key or ""
            # Không cần x-rapidapi-host
        # Nếu bạn cần thêm header khác (User-Agent, v.v.), thêm ở đây.

        # Gửi request
        try:
            method_upper = method.upper()
            if method_upper == "GET":
                response = self._session.get(url, headers=headers, timeout=self.timeout)
            else:
                # Với các method khác, gửi JSON body nếu muốn, hoặc form-data tuỳ API
                response = self._session.request(method_upper, url, headers=headers, json=params, timeout=self.timeout)
            # Kiểm tra HTTP status
            response.raise_for_status()
            # Parse JSON
            json_response = response.json()
            # Trích data và metadata
            data = json_response.get("response", [])
            metadata = {
                "paging": json_response.get("paging", {}),
                "results": json_response.get("results", 0)
            }
            return data, metadata

        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else None
            # Safe key hiển thị
            safe_key = self._safe_log_key(current_key)
            if status_code == 429:
                logger.warning(f"Rate limit exceeded or quota exceeded for key {safe_key}. Rotating key...")
                self._key_rotator.report_failure(current_key)
            elif status_code in (401, 403):
                logger.error(f"Invalid or unauthorized API key {safe_key}. Rotating key...")
                self._key_rotator.report_failure(current_key)
            # Log đầy đủ
            logger.error(f"HTTP error {status_code} from endpoint {endpoint_key}: {e}")
            # Rethrow để tenacity retry nếu phù hợp
            raise
        except (requests.ConnectionError, requests.Timeout) as e:
            safe_key = self._safe_log_key(current_key)
            logger.warning(f"Network error ({e}) with key {safe_key}. Rotating key...")
            self._key_rotator.report_failure(current_key)
            # Rethrow để tenacity retry
            raise
        except Exception as e:
            logger.exception(f"Unexpected error calling {endpoint_key}: {e}")
            raise

    def get_all_paginated_data(
        self,
        endpoint_key: str,
        params: Optional[Dict[str, Any]] = None,
        max_pages: int = 100
    ) -> List[Dict]:
        """
        Lấy toàn bộ dữ liệu phân trang tự động.
        Gọi call_api nhiều lần cho từng page, dừng khi hết pages hoặc lỗi.
        """
        all_data: List[Dict] = []
        page = 1
        while page <= max_pages:
            try:
                data, metadata = self.call_api(endpoint_key, params, page=page)
                all_data.extend(data)
                paging = metadata.get("paging", {})
                current = paging.get("current", page)
                total = paging.get("total", max_pages)
                logger.debug(f"Page {current}/{total} - {len(data)} records from {endpoint_key}")
                if current >= total:
                    break
                page = current + 1
            except Exception as e:
                logger.error(f"Failed to fetch page {page} for {endpoint_key}: {e}")
                break
        logger.info(f"Fetched total {len(all_data)} records from {endpoint_key}")
        return all_data

    def _safe_log_key(self, key: Optional[str]) -> str:
        """
        Hiển thị key an toàn: chỉ show 3 ký tự đầu + 3 ký tự cuối.
        """
        if not key or len(key) < 8:
            return "******"
        return f"{key[:3]}...{key[-3:]}"
