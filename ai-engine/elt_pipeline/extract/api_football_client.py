# ai-engine\elt_pipeline\extract\api_football_client.py

import logging
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tenacity import retry_if_exception 
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from config.settings import config
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
import threading
import hashlib

logger = logging.getLogger(__name__)

class APIFootballClient:
    """Client an toàn và mạnh mẽ cho API-Football với đầy đủ tính năng enterprise"""
    
    def __init__(self):
        self.base_url = config.api.base_url
        self.api_keys = [k.get_secret_value() for k in config.api.api_keys]
        self.timeout = 15
        self.rate_limit_delay = 0.1  # Giới hạn 10 requests/giây
        self._session = self._create_session()
        self._key_rotator = self.KeyRotator(self.api_keys)
        self._lock = threading.Lock()
        
    class KeyRotator:
        """Quản lý xoay vòng API key với cơ chế cooldown và thread-safe"""
        def __init__(self, keys: List[str]):
            self.keys = keys
            self.index = 0
            self.last_failed = {}
            self.cooldown = 300  # 5 phút cooldown
            
        def get_current_key(self) -> str:
            """Lấy key hiện tại một cách an toàn"""
            return self.keys[self.index]
        
        def next_key(self):
            """Chuyển sang key tiếp theo (thread-safe)"""
            self.index = (self.index + 1) % len(self.keys)
            
        def report_failure(self, key: str):
            """Đánh dấu key bị lỗi và chuyển sang key mới"""
            self.last_failed[key] = time.time()
            self.next_key()
            
        def is_key_ready(self, key: str) -> bool:
            """Kiểm tra key đã sẵn sàng sử dụng lại chưa"""
            return (time.time() - self.last_failed.get(key, 0)) > self.cooldown
        
        def all_keys_failed(self) -> bool:
            """Kiểm tra xem tất cả keys đều đang trong trạng thái cooldown"""
            return all(not self.is_key_ready(key) for key in self.keys)
    
    def _create_session(self) -> requests.Session:
        """Tạo session với retry policy và SSL verification"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=100)
        session.mount("https://", adapter)
        return session

    def _should_retry(self, e: Exception) -> bool:
        """Xác định khi nào nên retry request"""
        if isinstance(e, requests.HTTPError):
            return e.response.status_code in [429, 403, 401]
        return isinstance(e, (requests.ConnectionError, requests.Timeout))

    def _safe_log_key(self, key: str) -> str:
        """Log key an toàn chỉ hiển thị phần đầu và cuối"""
        if len(key) < 8:
            return "******"
        return f"{key[:3]}...{key[-3:]}"
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(lambda e: isinstance(e, (requests.HTTPError, requests.ConnectionError, requests.Timeout))),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def call_api(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        page: int = None,
        per_page: int = 100
    ) -> Tuple[List[Dict], Dict]:
        """
        Gọi API-Football với đầy đủ tính năng bảo mật và quản lý lỗi
        
        Args:
            endpoint: Tài nguyên API ("fixtures", "teams",...)
            params: Tham số truy vấn
            method: HTTP method ("GET" hoặc "POST")
            page: Trang dữ liệu (cho phân trang)
            per_page: Số bản ghi mỗi trang
            
        Returns:
            (data, metadata) - dữ liệu và thông tin phân trang
        """
        params = params or {}
        if page is not None:
            params.update({"page": page, "per_page": per_page})
        
        # Quản lý rate limiting
        time.sleep(self.rate_limit_delay)
        
        with self._lock:
            current_key = self._key_rotator.get_current_key()
            
            # Kiểm tra trạng thái key
            if not self._key_rotator.is_key_ready(current_key):
                self._key_rotator.next_key()
                current_key = self._key_rotator.get_current_key()
            
            # Circuit breaker: dừng nếu tất cả keys đều fail
            if self._key_rotator.all_keys_failed():
                logger.critical("All API keys exhausted! Service unavailable")
                raise RuntimeError("All API keys are in cooldown")
        
        headers = {
            "x-apisports-key": current_key,
            "Accept-Encoding": "gzip"
        }
        url = f"{self.base_url}/{endpoint}"
        
        try:
            # Sử dụng session đã tạo
            if method.upper() == "GET":
                response = self._session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.timeout,
                    verify=True  # Bật SSL verification
                )
            else:
                response = self._session.request(
                    method.upper(),
                    url,
                    headers=headers,
                    json=params,
                    timeout=self.timeout,
                    verify=True
                )
            
            response.raise_for_status()
            json_response = response.json()
            
            # Trả về dữ liệu + metadata phân trang
            data = json_response.get("response", [])
            metadata = {
                "paging": json_response.get("paging", {}),
                "results": json_response.get("results", 0)
            }
            return data, metadata
            
        except requests.HTTPError as e:
            status_code = e.response.status_code
            safe_key = self._safe_log_key(current_key)
            
            if status_code == 429:  # Quota exceeded
                logger.warning(f"API key quota exceeded for key {safe_key}. Rotating keys...")
                self._key_rotator.report_failure(current_key)
            elif status_code in (401, 403):  # Unauthorized/Forbidden
                logger.error(f"Invalid API key detected: {safe_key}")
                self._key_rotator.report_failure(current_key)
            
            logger.error(f"HTTP error {status_code} from {endpoint}: {str(e)}")
            raise
        
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.warning(f"Network error: {str(e)}. Rotating keys...")
            self._key_rotator.report_failure(current_key)
            raise
        
        except Exception as e:
            logger.exception(f"Unexpected API error: {str(e)}")
            raise

    def get_all_paginated_data(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        max_pages: int = 100
    ) -> List[Dict]:
        """Lấy toàn bộ dữ liệu phân trang tự động"""
        all_data = []
        page = 1
        total_pages = None
        
        while page <= max_pages:
            try:
                data, metadata = self.call_api(endpoint, params, page=page)
                all_data.extend(data)
                
                # Xử lý phân trang
                paging = metadata.get("paging", {})
                current = paging.get("current", page)
                total = paging.get("total", max_pages)
                
                logger.debug(f"Page {current}/{total} - {len(data)} records")
                
                # Kiểm tra đã lấy hết dữ liệu chưa
                if current >= total:
                    break
                    
                page = current + 1
                
            except Exception as e:
                logger.error(f"Failed to fetch page {page}: {str(e)}")
                break
                
        logger.info(f"Fetched {len(all_data)} records from {endpoint}")
        return all_data