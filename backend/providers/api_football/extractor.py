# backend\elt_pipeline\extract\api_football_client.py

import logging
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log, retry_if_exception
from typing import Any, Dict, List, Optional, Tuple

# Import module endpoint
from .endpoints import APIFootballEndpoints, build_url, get_rate_limit, APIFootballConfig

from config.settings import get_config

logger = logging.getLogger(__name__)

class APIFootballClient:
    """Client toàn diện cho API-Football với quản lý endpoint, rate limit và xoay key."""

    def __init__(self):
        # Get config instance
        self.config = get_config()
        # Validate config
        if not self.config.api.is_configured:
            raise RuntimeError("API Football configuration is incomplete. Check API_FOOTBALL_KEY environment variable.")
        
        # Extract API keys properly from settings
        self.api_keys: List[str] = [key for key in self.config.api.api_keys]
        
        if not self.api_keys:
            logger.warning("No API keys provided. Requests will use empty key.")
        
        # Timeout configuration - use reasonable default
        self.timeout = 30  # 30 seconds default timeout
        
        # Session với retry cơ bản cho HTTP status
        self._session = self._create_session()
        
        # Key rotator
        self._key_rotator = self.KeyRotator(self.api_keys)
        
        # Rate limiting tracking
        self._last_request_time = {}

    class KeyRotator:
        """Quản lý xoay vòng API key thông minh (không dùng threading lock)"""
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

        def get_available_key(self) -> Optional[str]:
            """Get next available key that's not in cooldown, or return current key if all are in cooldown."""
            if not self.keys:
                return None

            # Try each key once
            for _ in range(len(self.keys)):
                key = self.get_current_key()
                if key and self.is_key_ready(key):
                    return key
                self.next_key()

            # If all keys are in cooldown, just return the current key (even if not ready)
            return self.get_current_key()

    def _create_session(self) -> requests.Session:
        """
        Tạo session với retry policy cải thiện.
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],  
            raise_on_status=False  
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=50
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        # Set default headers
        session.headers.update({
            'User-Agent': 'Python-APIFootball-Client/1.0',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate'
        })
        
        return session

    def _enforce_rate_limit(self, endpoint: APIFootballEndpoints):
        """Enforce rate limiting per endpoint (no thread lock)"""
        rate_limit = get_rate_limit(endpoint)
        min_interval = 1.0 / rate_limit
        endpoint_key = endpoint.value
        last_time = self._last_request_time.get(endpoint_key, 0)
        time_since_last = time.time() - last_time
        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for {endpoint_key}")
            time.sleep(sleep_time)
        self._last_request_time[endpoint_key] = time.time()

    @staticmethod
    def _should_retry(e: Exception) -> bool:
        """
        Logic để tenacity quyết định có retry hay không
        """
        if isinstance(e, requests.HTTPError):
            if not e.response:
                return True
            status = e.response.status_code
            # Retry on server errors and rate limits, but not auth errors
            return status in [429, 500, 502, 503, 504]
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
        page: Optional[int] = 0,
        per_page: int = 1
    ) -> Tuple[List[Dict], Dict]:
        """
        Gọi API-Football với enhanced error handling và rate limiting.
        """
        # Validate input
        if method.upper() != "GET":
            raise ValueError("API-Football only supports GET requests")
        # Prepare params
        params = params.copy() if params else {}
        if page is not None:
            params["page"] = page
        if per_page != 100:  # Only add if different from default
            params["per_page"] = per_page

        # Convert endpoint_key to Enum
        try:
            endpoint_enum = APIFootballEndpoints.from_string(endpoint_key)
        except ValueError as e:
            logger.error(f"Invalid endpoint: {e}")
            raise

        # Enforce rate limiting
        self._enforce_rate_limit(endpoint_enum)

        # Get available API key
        # current_key = self._key_rotator.get_available_key()
        current_key = "bcb590d87f95ea462c817e9716b42a6a"
        
        if not current_key:
            raise RuntimeError("No API keys available")

        # Check if all keys are in cooldown
        if self._key_rotator.all_keys_failed():
            logger.critical("All API keys are in cooldown. Service temporarily unavailable.")
            raise RuntimeError("All API keys exhausted. Please wait before retrying.")
        # Build URL
        try:
            url = build_url(endpoint_enum)#m, params)
        except Exception as e:
            logger.error(f"Failed to build URL for endpoint {endpoint_enum}: {e}")
            raise
        logger.debug(f"Using API key: {self._safe_log_key(current_key)} for endpoint {endpoint_enum}")
        # Prepare headers - use direct API-Football format
        headers = {
            "x-apisports-key": current_key,
            "Accept-Encoding": "gzip"
        }
        # Make request
        try:
            logger.debug(f"Making request to {endpoint_key} with params: {params}")
            response = self._session.get(url, headers=headers, timeout=self.timeout)
            # print(response.content)
            # print("oke")
            # Handle response
            return self._handle_response(response, current_key, endpoint_key)
            
        except requests.HTTPError as e:
            self._handle_http_error(e, current_key, endpoint_key)
            raise
        except (requests.ConnectionError, requests.Timeout) as e:
            self._handle_network_error(e, current_key, endpoint_key)
            raise
        except Exception as e:
            logger.exception(f"Unexpected error calling {endpoint_key}: {e}")
            raise

    def _handle_response(self, response: requests.Response, current_key: str, endpoint_key: str) -> Tuple[List[Dict], Dict]:
        """Handle API response with proper error checking"""
        try:
            # Check HTTP status
            if response.status_code == 429:
                logger.warning(f"Rate limit exceeded for key {self._safe_log_key(current_key)}")
                self._key_rotator.report_failure(current_key)
                raise requests.HTTPError(f"Rate limit exceeded", response=response)
            
            elif response.status_code in (401, 403):
                logger.error(f"Authentication failed for key {self._safe_log_key(current_key)}")
                self._key_rotator.report_failure(current_key)
                raise requests.HTTPError(f"Authentication failed: {response.status_code}", response=response)
            
            elif response.status_code >= 400:
                logger.error(f"HTTP {response.status_code} error for {endpoint_key}: {response.text[:200]}...")
                raise requests.HTTPError(f"HTTP {response.status_code}", response=response)
            
            # Parse JSON response
            try:
                json_response = response.json()
            except ValueError as e:
                logger.error(f"Invalid JSON response from {endpoint_key}: {e}")
                raise ValueError(f"Invalid JSON response: {e}")
            
            # Check API-specific errors
            if "errors" in json_response and json_response["errors"]:
                errors = json_response["errors"]
                logger.error(f"API returned errors for {endpoint_key}: {errors}")
                raise RuntimeError(f"API errors: {errors}")
            
            # Extract data
            data = json_response.get("response", [])
            metadata = {
                "paging": json_response.get("paging", {}),
                "results": json_response.get("results", 0),
                "errors": json_response.get("errors", [])
            }
            
            logger.debug(f"Successfully fetched {len(data)} records from {endpoint_key}")
            return data, metadata
            
        except Exception as e:
            logger.error(f"Error handling response for {endpoint_key}: {e}")
            raise

    def _handle_http_error(self, error: requests.HTTPError, current_key: str, endpoint_key: str):
        """Handle HTTP errors with proper logging and key rotation"""
        status_code = error.response.status_code if error.response else None
        safe_key = self._safe_log_key(current_key)
        
        if status_code == 429:
            logger.warning(f"Rate limit exceeded for key {safe_key} on {endpoint_key}")
            self._key_rotator.report_failure(current_key)
        elif status_code in (401, 403):
            logger.error(f"Authentication failed for key {safe_key} on {endpoint_key}")
            self._key_rotator.report_failure(current_key)
        else:
            logger.error(f"HTTP {status_code} error for {endpoint_key} with key {safe_key}")

    def _handle_network_error(self, error: Exception, current_key: str, endpoint_key: str):
        """Handle network errors with proper logging and key rotation"""
        safe_key = self._safe_log_key(current_key)
        logger.warning(f"Network error ({type(error).__name__}) for {endpoint_key} with key {safe_key}: {error}")
        # Don't rotate key for network errors - might not be key-related

    def get_all_paginated_data(
        self,
        endpoint_key: str,
        params: Optional[Dict[str, Any]] = None,
        max_pages: int = 100,
        per_page: int = 100
    ) -> List[Dict]:
        """
        Lấy toàn bộ dữ liệu phân trang với improved logic.
        """
        all_data: List[Dict] = []
        page = 1
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        logger.info(f"Starting paginated fetch for {endpoint_key} (max_pages: {max_pages})")
        
        while page <= max_pages:
            try:
                data, metadata = self.call_api(endpoint_key, params, page=page, per_page=per_page)
                
                # Reset error counter on success
                consecutive_errors = 0
                
                all_data.extend(data)
                
                # Check pagination info
                paging = metadata.get("paging", {})
                current = paging.get("current", page)
                total = paging.get("total", 1)
                
                logger.debug(f"Page {current}/{total} - {len(data)} records from {endpoint_key}")
                
                # Break if no more data or reached end
                if len(data) == 0 or current >= total:
                    logger.info(f"Reached end of data at page {current}")
                    break
                
                page = current + 1
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Failed to fetch page {page} for {endpoint_key}: {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many consecutive errors ({consecutive_errors}). Stopping pagination.")
                    break
                
                # Try next page after error
                page += 1
        
        logger.info(f"Fetched total {len(all_data)} records from {endpoint_key} across {page-1} pages")
        return all_data

    def test_connection(self) -> bool:
        """Test API connection with a simple endpoint"""
        try:
            logger.info("Testing API connection...")
            data, metadata = self.call_api("TIMEZONES")
            logger.info(f"Connection test successful. Got {len(data)} timezones.")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def get_api_status(self) -> Dict[str, Any]:
        """Get API status information"""
        return {
            "total_keys": len(self.api_keys),
            "available_keys": len([k for k in self.api_keys if self._key_rotator.is_key_ready(k)]),
            "current_key": self._safe_log_key(self._key_rotator.get_current_key()),
            "all_keys_failed": self._key_rotator.all_keys_failed(),
            "rate_limits": {ep.name: get_rate_limit(ep) for ep in APIFootballEndpoints}
        }

    def _safe_log_key(self, key: Optional[str]) -> str:
        """
        Hiển thị key an toàn: chỉ show 4 ký tự đầu + 4 ký tự cuối.
        """
        if not key or len(key) < 12:
            return "***masked***"
        return f"{key[:4]}...{key[-4:]}"