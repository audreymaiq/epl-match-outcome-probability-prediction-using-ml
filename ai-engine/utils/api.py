# utils/api.py

import logging
from typing import Any, Dict, Optional, List
import requests
import json
import time
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception, before_sleep_log
from config import API_FOOTBALL_CONFIG

logger = logging.getLogger(__name__)

# Quản lý trạng thái xoay vòng keys
class APIKeyRotator:
    def __init__(self, keys: List[str]):
        self.keys = keys
        self.index = 0
        self.last_failed = {}  # Lưu thời điểm key bị lỗi
        self.cooldown = 300  # 5 phút (thời gian chờ trước khi thử lại key lỗi)
    
    def get_current_key(self) -> str:
        """Lấy key hiện tại và tự động xoay vòng"""
        return self.keys[self.index]
    
    def next_key(self):
        """Chuyển sang key tiếp theo"""
        self.index = (self.index + 1) % len(self.keys)
        logger.info(f"Switched to API key index {self.index}")
    
    def report_failure(self, key: str):
        """Đánh dấu key hiện tại bị lỗi"""
        self.last_failed[key] = time.time()
        self.next_key()
    
    def is_key_ready(self, key: str) -> bool:
        """Kiểm tra key đã sẵn sàng dùng lại chưa"""
        if key not in self.last_failed:
            return True
        return (time.time() - self.last_failed[key]) > self.cooldown

# Khởi tạo key rotator
key_rotator = APIKeyRotator(API_FOOTBALL_CONFIG['api_key'])

# Kiểm tra lỗi cần xoay vòng key
def should_retry_with_new_key(e: Exception) -> bool:
    if isinstance(e, requests.HTTPError):
        return e.response.status_code in [429, 403, 401]  # Quota exceeded, forbidden, unauthorized
    return isinstance(e, (requests.ConnectionError, requests.Timeout))

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(10),
    retry=retry_if_exception(should_retry_with_new_key),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def call_api_football(
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    method: str = "GET",
    response_key: str = "response",
) -> Any:
    """
    Gọi API-Football với cơ chế xoay vòng API keys tự động
    
    Args:
        endpoint: Ví dụ: "teams", "fixtures", ...
        params: Query/body params
        method: "GET" hoặc "POST"
        response_key: Key chứa dữ liệu trong response (mặc định "response")
    
    Returns:
        Dữ liệu từ API hoặc [] nếu không có
    """
    params = params or {}
    current_key = key_rotator.get_current_key()
    
    headers = {
        "x-apisports-key": current_key
    }
    url = f"{API_FOOTBALL_CONFIG['base_url']}/{endpoint}"
    
    # Kiểm tra nếu key hiện tại đang trong trạng thái chờ
    if not key_rotator.is_key_ready(current_key):
        key_rotator.next_key()
        current_key = key_rotator.get_current_key()
        headers["x-apisports-key"] = current_key

    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=15)
        else:
            response = requests.request(method, url, headers=headers, json=params, timeout=15)
        
        response.raise_for_status()
        return response.json().get(response_key, [])
    
    except requests.HTTPError as e:
        status_code = e.response.status_code
        if status_code == 429:  # Quota exceeded
            logger.warning(f"API key quota exceeded. Rotating keys...")
            key_rotator.report_failure(current_key)
        
        logger.error(f"HTTP error {status_code} from {url}: {str(e)}")
        raise
    
    except (requests.ConnectionError, requests.Timeout) as e:
        logger.warning(f"Network error: {str(e)}. Retrying with new key...")
        key_rotator.report_failure(current_key)
        raise
    
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response from {url}: {str(e)}")
        return []