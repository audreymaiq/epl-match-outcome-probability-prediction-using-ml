# # elt_pipeline\extract\sofascore_extractor.py

# """
# SofaScore ETL Pipeline: Client: Chỉ fetch dữ liệu thô từ API.
# """

# import time
# import logging
# from typing import List, Dict, Any, Optional
# from curl_cffi.requests import Session, RequestsError
# from pybreaker import CircuitBreaker, CircuitBreakerError

# # Import các thành phần từ kiến trúc đã xây dựng
# from config.settings import SofascoreSettings, ScrapingSettings
# from elt_pipeline.extract.sofascore_endpoints import (
#     SofaScoreEndpoints, build_url, get_headers,
#     get_rate_limit_per_second, validate_endpoint_params, get_timeout_settings
# )

# # --- Cấu hình ban đầu ---
# logger = logging.getLogger(__name__)

# # --- LỚP CLIENT: CHỈ GIAO TIẾP HTTP ---
# class SofaScoreExtractor:
#     """Chỉ chịu trách nhiệm gửi request và nhận response thô từ SofaScore API."""

#     def __init__(self, sofascore_config: SofascoreSettings, scraping_config: ScrapingSettings):
#         self.sofascore_config = sofascore_config
#         self.scraping_config = scraping_config
#         self.session = Session(
#             impersonate=self.scraping_config.browser_impersonate,
#             verify=not self.scraping_config.ignore_ssl_errors
#         )
#         logger.info(f"SofaScoreExtractor initialized, impersonating: '{self.scraping_config.browser_impersonate}'")

#     def _make_request(
#         self,
#         endpoint: SofaScoreEndpoints,
#         params: Optional[Dict] = None,
#         breaker: Optional[CircuitBreaker] = None,
#         **kwargs
#     ) -> Optional[Dict[str, Any]]:
#         """
#         Phương thức private để thực hiện request với retry, delay và config động.
#         """
#         validate_endpoint_params(endpoint, **kwargs)
#         base_web_url = str(self.sofascore_config.web_base_url).rstrip('/')
#         referer = f"{base_web_url}/football/england/premier-league/{self.sofascore_config.premier_league_id}"
#         if 'match_id' in kwargs:
#             referer = f"{base_web_url}/football/match-slug/{kwargs['match_id']}"
#         elif 'team_id' in kwargs:
#             referer = f"{base_web_url}/team/{kwargs['team_id']}"

#         url = build_url(endpoint, params, **kwargs)
#         headers = get_headers(endpoint, referer=referer)

#         connect_timeout, read_timeout = get_timeout_settings(endpoint)
#         timeout_tuple = (connect_timeout, read_timeout)

#         rate_limit_rps = get_rate_limit_per_second(endpoint)
#         base_delay = 1.0 / rate_limit_rps if rate_limit_rps > 0 else 1.0

#         max_retries = self.scraping_config.max_retries
#         backoff_factor = self.scraping_config.backoff_factor

#         for attempt in range(max_retries):
#             try:
#                 # Hàm thực thi request thực tế
#                 def _execute_get() -> Optional[Dict[str, Any]]:
#                     random_delay = self.scraping_config.get_random_delay()
#                     total_delay = (base_delay + random_delay) * (backoff_factor ** attempt)
#                     if attempt > 0 or base_delay > 0:
#                         time.sleep(total_delay)

#                     proxy = self.scraping_config.get_random_proxy()
#                     proxies = {"http": proxy, "https": proxy} if proxy else None

#                     log_extra = {
#                         "url": url, "attempt": attempt + 1, "timeout": timeout_tuple,
#                         "proxy": "Yes" if proxy else "No", "sleep": round(total_delay, 2)
#                     }
#                     logger.debug("Making request", extra=log_extra)

#                     response = self.session.get(url, headers=headers, timeout=timeout_tuple , proxies=proxies)

#                     if response.status_code == 404:
#                         logger.warning("Resource not found (404)", extra={"url": url})
#                         return None

#                     response.raise_for_status()
#                     return response.json()

#                 if breaker:
#                     # breaker.call sẽ tự xử lý exception và đếm lỗi
#                     return breaker.call(_execute_get)
#                 else:
#                     # Nếu không có breaker, gọi thẳng
#                     return _execute_get()

#             except CircuitBreakerError as e:
#                 logger.error(f"Circuit Breaker is open. Aborting request to {url}. Error: {e}")
#                 raise # Ném lại để tầng trên (Orchestrator) xử lý

#             except RequestsError as e:
#                 logger.warning(
#                     "Request attempt failed with a network error.",
#                     extra={"url": url, "attempt": attempt + 1, "max_retries": max_retries, "original_error": str(e)}
#                 )
#                 if attempt == max_retries - 1:
#                     logger.error("Max retries exceeded for request.", extra={"url": url})
#                     return None
#         return None
    
#     def fetch_paginated_data(
#         self, 
#         endpoint: SofaScoreEndpoints, 
#         response_field: str,
#         breaker: Optional[CircuitBreaker] = None, 
#         **kwargs
#     ) -> tuple[List[Dict], int]:
#         """Fetch dữ liệu từ các endpoint có phân trang và trả về số request đã thực hiện."""
        
#         if not response_field:
#             raise ValueError("response_field must be a non-empty string.")
        
#         all_items = []
#         page = 0
#         requests_made = 0
#         empty_page_strikes = 0
#         MAX_EMPTY_STRIKES = 2
                
#         while empty_page_strikes < MAX_EMPTY_STRIKES:
#             page += 1
            
#             # SỬA LỖI: Gộp tất cả các tham số cần thiết cho việc format URL vào một chỗ.
#             # `kwargs` chứa các tham số như tournament_id, season_id.
#             # Chúng ta thêm 'page' vào đó.
#             url_format_params = kwargs.copy()
#             url_format_params['page'] = page
            
#             try:
#                 # Bây giờ, tất cả các tham số cần để format URL (bao gồm cả page)
#                 # đều được truyền qua **url_format_params.
#                 # Không cần dùng tham số `params` nữa.
#                 data = self._make_request(endpoint, breaker=breaker, **url_format_params)
#                 requests_made += 1
                
#                 if data is None:
#                     empty_page_strikes += 1
#                     logger.info(f"No data received (strike {empty_page_strikes}/{MAX_EMPTY_STRIKES})", extra={"endpoint": endpoint.name, "page": page})
#                     continue
                
#                 items = data.get(response_field, [])
                
#                 if not isinstance(items, list):
#                     logger.warning(f"Invalid response structure. Expected list for key '{response_field}', got {type(items)}", extra={"endpoint": endpoint.name, "page": page})
#                     empty_page_strikes += 1
#                     continue
                    
#                 if not items:
#                     empty_page_strikes += 1
#                     logger.info(f"Empty page detected for key '{response_field}' (strike {empty_page_strikes}/{MAX_EMPTY_STRIKES})", extra={"endpoint": endpoint.name, "page": page})
#                     continue

#                 empty_page_strikes = 0
#                 all_items.extend(items)
                
#             except CircuitBreakerError:
#                 logger.warning(f"Stopping pagination for {endpoint.name} as circuit breaker is open.")
#                 break
#             except Exception as e:
#                 logger.error(f"Unexpected error during pagination", extra={"endpoint": endpoint.name, "page": page, "error": str(e)}, exc_info=True)
#                 requests_made += 1
#                 empty_page_strikes += 1
                
#         logger.info(f"Pagination finished for key '{response_field}' after {page} pages.", extra={"endpoint": endpoint.name, "total_items": len(all_items)})        
#         return all_items, requests_made

#     def fetch_match_detail(self, match_id: int, breaker: Optional[CircuitBreaker] = None) -> Optional[Dict]:
#         """Wrapper đơn giản để lấy chi tiết trận đấu. Trả về toàn bộ JSON response."""
#         try:
#             return self._make_request(SofaScoreEndpoints.MATCH_DETAIL, breaker=breaker, match_id=match_id)
#         except CircuitBreakerError:
#             return None

#     def fetch_lineups(self, match_id: int, breaker: Optional[CircuitBreaker] = None) -> Optional[Dict]:
#         """Wrapper để lấy đội hình. Trả về toàn bộ JSON response."""
#         try:
#             return self._make_request(SofaScoreEndpoints.MATCH_LINEUPS, breaker=breaker, match_id=match_id)
#         except CircuitBreakerError:
#             return None

#     def fetch_statistics(self, match_id: int, breaker: Optional[CircuitBreaker] = None) -> Optional[Dict]:
#         """Wrapper để lấy thống kê. Trả về toàn bộ JSON response."""
#         try:
#             return self._make_request(SofaScoreEndpoints.MATCH_STATISTICS, breaker=breaker, match_id=match_id)
#         except CircuitBreakerError:
#             return None

#     def fetch_incidents(self, match_id: int, breaker: Optional[CircuitBreaker] = None) -> Optional[Dict]:
#         """Wrapper để lấy các sự kiện. Trả về toàn bộ JSON response."""
#         try:
#             return self._make_request(SofaScoreEndpoints.MATCH_INCIDENTS, breaker=breaker, match_id=match_id)
#         except CircuitBreakerError:
#             return None

#     def fetch_paginated_events(self, endpoint: SofaScoreEndpoints, breaker: Optional[CircuitBreaker] = None, **kwargs) -> List[Dict]:
#         """Alias for fetch_paginated_data, mặc định lấy key 'events'."""
#         items, _ = self.fetch_paginated_data(endpoint, response_field="events", breaker=breaker, **kwargs)
#         return items

#     def close(self):
#         """Đóng session khi hoàn tất."""
#         self.session.close()
#         logger.info("SofaScoreClient session closed.")


# ai-engine\elt_pipeline\extract\sofascore_extractor.py 

"""
Mục đích tổng thể của file:
Đây là lớp (Class) chịu trách nhiệm chính cho việc giao tiếp với API của SofaScore.
Nó không chỉ đơn giản là gửi request HTTP, mà còn triển khai nhiều cơ chế quan trọng
để việc trích xuất dữ liệu (Extract) trở nên mạnh mẽ, đáng tin cậy và "lịch sự" với server của SofaScore.

Các tính năng và quyết định thiết kế chính:
1.  Rate Limiting: Giới hạn tần suất gửi request để tránh bị chặn IP do gửi quá nhiều yêu cầu trong thời gian ngắn.
2.  Retry with Exponential Backoff: Tự động thử lại các request thất bại, với thời gian chờ tăng dần sau mỗi lần thử,
    giúp xử lý các lỗi mạng tạm thời.
3.  Circuit Breaker (Bộ ngắt mạch): Một mẫu thiết kế nâng cao để ngăn ứng dụng liên tục gửi request đến một dịch vụ
    đang gặp sự cố, giúp hệ thống tự phục hồi nhanh hơn.
4.  Impersonation: Sử dụng `curl-cffi` để giả lập (impersonate) một trình duyệt thật, vượt qua các cơ chế chống bot
    cơ bản của các trang web.
5.  Centralized Logic: Toàn bộ logic giao tiếp với SofaScore API được đóng gói trong lớp này, giúp các phần khác của
    ứng dụng (ví dụ: các pipeline) chỉ cần gọi các phương thức đơn giản như `fetch_match_detail()` mà không cần
    quan tâm đến sự phức tạp bên trong.
6.  Sử dụng cấu hình động: Lớp nhận các đối tượng cấu hình (`SofascoreSettings`, `ScrapingSettings`) khi khởi tạo,
    giúp nó linh hoạt và dễ dàng thay đổi hành vi (như URL, số lần retry, timeout) mà không cần sửa code.
"""

import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlencode
from curl_cffi.requests import Session, RequestsError
from pybreaker import CircuitBreaker, CircuitBreakerError

from config.settings import SofascoreSettings, ScrapingSettings
from .sofascore_endpoints import SofaScoreEndpoints

logger = logging.getLogger(__name__)

class SofaScoreExtractor:
    def __init__(self, sofascore_config: SofascoreSettings, scraping_config: ScrapingSettings):
        """
        Phương thức khởi tạo (constructor) của lớp.
        Nó được gọi khi một đối tượng mới của lớp `SofaScoreExtractor` được tạo ra.
        """
        self.config = sofascore_config
        self.scraping_config = scraping_config
        self.base_url = str(self.config.base_url).rstrip('/')
        
        self.session = Session(
            impersonate=self.scraping_config.browser_impersonate,
            verify=not self.scraping_config.ignore_ssl_errors
        )
        self._last_request_time = 0
        self._request_interval = 60.0 / self.config.requests_per_minute
        logger.info(f"SofaScoreExtractor initialized. Base URL: {self.base_url}, Request Interval: {self._request_interval:.2f}s")

    def _build_url(self, endpoint: SofaScoreEndpoints, params: Optional[Dict] = None, **kwargs) -> str:
        """
        Xây dựng URL hoàn chỉnh để gọi API.
        - `endpoint`: Một thành viên của Enum `SofaScoreEndpoints`.
        - `params`: Dictionary cho các query parameters (phần sau dấu `?`).
        - `**kwargs`: Các tham số động để điền vào placeholder trong URL (ví dụ: `match_id=123`).
        """        
        required_params = endpoint.get_required_params()
        missing_params = required_params - set(kwargs.keys())
        if missing_params:
            raise ValueError(f"Missing required params for {endpoint.name}: {missing_params}")

        path = endpoint.value.format(**kwargs)
        full_url = f"{self.base_url}{path}"
        
        if params:
            clean_params = {k: v for k, v in params.items() if v is not None}
            if clean_params:
                full_url += "?" + urlencode(clean_params)
        return full_url

    def _rate_limit(self):
        """Thực thi cơ chế giới hạn tần suất request."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._request_interval:
            sleep_time = self._request_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
        self._last_request_time = time.monotonic()

    def _execute_with_retry(self, url: str, referer: Optional[str] = None, breaker: Optional[CircuitBreaker] = None) -> Optional[Dict[str, Any]]:
        """
        Hàm cốt lõi để thực thi một request với cơ chế retry, rate limiting và circuit breaker.
        - `breaker`: Một đối tượng `CircuitBreaker` tùy chọn.
        """
        max_retries = self.scraping_config.max_retries
        backoff_factor = self.scraping_config.backoff_factor
        
        for attempt in range(max_retries):
            try:
                def _request_func():
                    self._rate_limit()
                    log_extra = {"url": url, "attempt": attempt + 1}
                    logger.info("Making request", extra=log_extra)
                    
                    # *** SỬA LỖI: GỌI ĐÚNG PHƯƠNG THỨC get_headers() TỪ CONFIG ***
                    request_headers = self.config.get_headers(referer=referer)
                    timeout = (self.scraping_config.connect_timeout, self.scraping_config.read_timeout)
                    
                    response = self.session.get(url, headers=request_headers, timeout=timeout)
                    
                    if response.status_code == 404:
                        logger.warning("Resource not found (404)", extra={"url": url})
                        return None
                    
                    response.raise_for_status()
                    return response.json()

                if breaker:
                    return breaker.call(_request_func)
                else:
                    return _request_func()

            except CircuitBreakerError as e:
                logger.error(f"Circuit Breaker is open. Aborting request to {url}. Error: {e}")
                return None
            except RequestsError as e:
                if attempt == max_retries - 1:
                    logger.error("Max retries exceeded for request.", extra={"url": url, "error": str(e)})
                    return None
                delay = (self._request_interval * (backoff_factor ** attempt))
                time.sleep(delay)
        return None

    def _build_referer(self, **kwargs) -> str:
        """
        Xây dựng header `Referer` 
        Header `Referer` cho server biết request đến từ trang nào. Đây là một kỹ thuật quan trọng
        để làm cho request trông giống như một người dùng thật đang duyệt web.
        """
        web_base_url = str(self.config.web_base_url)
        if 'match_id' in kwargs:
            return f"{web_base_url}/event/{kwargs['match_id']}"
        return f"{web_base_url}/football/england/premier-league/{self.config.premier_league_id}"

    # --- CÁC PHƯƠG THỨC PUBLIC ---
    # Đây là "giao diện" của lớp, các phần khác của ứng dụng sẽ gọi các phương thức này.
    # Chúng đều có cấu trúc tương tự nhau:
    # 1. Xây dựng URL.
    # 2. Xây dựng Referer.
    # 3. Gọi `_execute_with_retry` để thực hiện request.

    def fetch_match_detail(self, match_id: int, breaker: Optional[CircuitBreaker] = None) -> Optional[Dict]:
        url = self._build_url(SofaScoreEndpoints.MATCH_DETAIL, match_id=match_id)
        referer = self._build_referer(match_id=match_id)
        return self._execute_with_retry(url, referer=referer, breaker=breaker)

    def fetch_lineups(self, match_id: int, breaker: Optional[CircuitBreaker] = None) -> Optional[Dict]:
        url = self._build_url(SofaScoreEndpoints.MATCH_LINEUPS, match_id=match_id)
        referer = self._build_referer(match_id=match_id)
        return self._execute_with_retry(url, referer=referer, breaker=breaker)

    def fetch_statistics(self, match_id: int, breaker: Optional[CircuitBreaker] = None) -> Optional[Dict]:
        url = self._build_url(SofaScoreEndpoints.MATCH_STATISTICS, match_id=match_id)
        referer = self._build_referer(match_id=match_id)
        return self._execute_with_retry(url, referer=referer, breaker=breaker)

    def fetch_incidents(self, match_id: int, breaker: Optional[CircuitBreaker] = None) -> Optional[Dict]:
        url = self._build_url(SofaScoreEndpoints.MATCH_INCIDENTS, match_id=match_id)
        referer = self._build_referer(match_id=match_id)
        return self._execute_with_retry(url, referer=referer, breaker=breaker)

    def fetch_paginated_data(self, endpoint: SofaScoreEndpoints, response_field: str, breaker: Optional[CircuitBreaker] = None, **kwargs) -> Tuple[List[Dict], bool]:
        """
        Một phương thức tổng quát để lấy dữ liệu từ các endpoint có phân trang (pagination).
        - `response_field`: Tên của trường trong JSON response chứa danh sách các mục (ví dụ: 'events', 'players').
        - `**kwargs`: Các tham số cần thiết cho endpoint (ví dụ: `tournament_id`, `season_id`).
        """
        all_items = []
        page = 0
        while True:
            page += 1
            url = self._build_url(endpoint, page=page, **kwargs)
            referer = self._build_referer(**kwargs)
            response_data = self._execute_with_retry(url, referer=referer, breaker=breaker)
            
            if not response_data or not (items := response_data.get(response_field, [])):
                break
            
            all_items.extend(items)
            if not response_data.get('hasNextPage', False):
                break
        return all_items, len(all_items) > 0

    def close(self):
        """
        Phương thức dọn dẹp, đóng session lại để giải phóng tài nguyên.
        Nên được gọi khi đối tượng Extractor không còn được sử dụng nữa.
        """
        self.session.close()
        logger.info("SofaScoreExtractor session closed.")