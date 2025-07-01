# elt_pipeline\extract\sofascore_extractor.py

"""
SofaScore ETL Pipeline: Client: Chỉ fetch dữ liệu thô từ API.
"""

import time
import logging
from typing import List, Dict, Any, Optional
from curl_cffi.requests import Session, RequestsError
from pybreaker import CircuitBreaker, CircuitBreakerError

# Import các thành phần từ kiến trúc đã xây dựng
from config.settings import SofascoreSettings, ScrapingSettings
from elt_pipeline.extract.sofascore_endpoints import (
    SofaScoreEndpoints, build_url, get_headers,
    get_rate_limit_per_second, validate_endpoint_params, get_timeout_settings
)

# --- Cấu hình ban đầu ---
logger = logging.getLogger(__name__)

# --- LỚP CLIENT: CHỈ GIAO TIẾP HTTP ---
class SofaScoreExtractor:
    """Chỉ chịu trách nhiệm gửi request và nhận response thô từ SofaScore API."""

    def __init__(self, sofascore_config: SofascoreSettings, scraping_config: ScrapingSettings):
        self.sofascore_config = sofascore_config
        self.scraping_config = scraping_config
        self.session = Session(
            impersonate=self.scraping_config.browser_impersonate,
            verify=not self.scraping_config.ignore_ssl_errors
        )
        logger.info(f"SofaScoreExtractor initialized, impersonating: '{self.scraping_config.browser_impersonate}'")

    def _make_request(
        self,
        endpoint: SofaScoreEndpoints,
        params: Optional[Dict] = None,
        breaker: Optional[CircuitBreaker] = None,
        **kwargs
    ) -> Optional[Any]:
        """
        Phương thức private để thực hiện request với retry, delay và config động.
        """
        validate_endpoint_params(endpoint, **kwargs)
        base_web_url = str(self.sofascore_config.web_base_url).rstrip('/')
        referer = f"{base_web_url}/football/england/premier-league/{self.sofascore_config.premier_league_id}"
        if 'match_id' in kwargs:
            referer = f"{base_web_url}/football/match-slug/{kwargs['match_id']}"
        elif 'team_id' in kwargs:
            referer = f"{base_web_url}/team/{kwargs['team_id']}"

        url = build_url(endpoint, params, **kwargs)
        headers = get_headers(endpoint, referer=referer)

        connect_timeout, read_timeout = get_timeout_settings(endpoint)
        timeout_tuple = (connect_timeout, read_timeout)

        rate_limit_rps = get_rate_limit_per_second(endpoint)
        base_delay = 1.0 / rate_limit_rps if rate_limit_rps > 0 else 1.0

        max_retries = self.scraping_config.max_retries
        backoff_factor = self.scraping_config.backoff_factor

        for attempt in range(max_retries):
            try:
                # Hàm thực thi request thực tế
                def _execute_get():
                    random_delay = self.scraping_config.get_random_delay()
                    total_delay = (base_delay + random_delay) * (backoff_factor ** attempt)
                    if attempt > 0 or base_delay > 0:
                        time.sleep(total_delay)

                    proxy = self.scraping_config.get_random_proxy()
                    proxies = {"http": proxy, "https": proxy} if proxy else None

                    log_extra = {
                        "url": url, "attempt": attempt + 1, "timeout": timeout_tuple,
                        "proxy": "Yes" if proxy else "No", "sleep": round(total_delay, 2)
                    }
                    logger.debug("Making request", extra=log_extra)

                    response = self.session.get(url, headers=headers, timeout=timeout_tuple , proxies=proxies)

                    if response.status_code == 404:
                        logger.warning("Resource not found (404)", extra={"url": url})
                        return None

                    response.raise_for_status()
                    return response.json()

                if breaker:
                    # breaker.call sẽ tự xử lý exception và đếm lỗi
                    return breaker.call(_execute_get)
                else:
                    # Nếu không có breaker, gọi thẳng
                    return _execute_get()

            except CircuitBreakerError as e:
                logger.error(f"Circuit Breaker is open. Aborting request to {url}. Error: {e}")
                raise

            except RequestsError as e:
                logger.warning(
                    "Request attempt failed with a network error.",
                    extra={
                        "url": url,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "original_error": str(e)
                    }
                )
                if attempt == max_retries - 1:
                    logger.error("Max retries exceeded for request.", extra={"url": url})
                    return None
        return None
    
    def fetch_paginated_data(self, endpoint: SofaScoreEndpoints, breaker: Optional[CircuitBreaker] = None, **kwargs) -> tuple[List[Dict], int]:
        """Fetch dữ liệu từ các endpoint có phân trang và trả về số request đã thực hiện."""
        all_items = []
        page = 0
        requests_made = 0
        empty_page_strikes = 0
        MAX_EMPTY_STRIKES = 2
        
        # Determine the response field based on endpoint
        response_field = "events"  # Default, có thể customize based on endpoint type
        
        while empty_page_strikes < MAX_EMPTY_STRIKES:
            page += 1
            kwargs['page'] = page
            
            try:
                data = self._make_request(endpoint, breaker=breaker, **kwargs)
                requests_made += 1
                
                if data is None:
                    empty_page_strikes += 1
                    logger.info(f"No data received (strike {empty_page_strikes}/{MAX_EMPTY_STRIKES})", 
                            extra={"endpoint": endpoint.name, "page": page})
                    continue
                
                items = data.get(response_field, [])
                
                # Validate response structure
                if not isinstance(items, list):
                    logger.warning(f"Invalid response structure. Expected list, got {type(items)}", 
                                extra={"endpoint": endpoint.name, "page": page})
                    empty_page_strikes += 1
                    continue
                    
                if not items:
                    empty_page_strikes += 1
                    logger.info(f"Empty page detected (strike {empty_page_strikes}/{MAX_EMPTY_STRIKES})", 
                            extra={"endpoint": endpoint.name, "page": page})
                    continue

                empty_page_strikes = 0
                all_items.extend(items)
                
            except CircuitBreakerError:
                logger.warning(f"Stopping pagination for {endpoint.name} as circuit breaker is open.")
                break
            except Exception as e:
                logger.error(f"Unexpected error during pagination", 
                            extra={"endpoint": endpoint.name, "page": page, "error": str(e)})
                requests_made += 1  # Count failed requests too
                empty_page_strikes += 1
                
        logger.info(f"Pagination finished after {page} pages and {empty_page_strikes} empty strikes.", 
                extra={"endpoint": endpoint.name, "total_items": len(all_items)})        
        return all_items, requests_made

    def fetch_match_detail(self, match_id: int, breaker: Optional[CircuitBreaker] = None) -> Optional[Dict]:
        """Wrapper đơn giản để lấy chi tiết trận đấu."""
        try:
            data = self._make_request(SofaScoreEndpoints.MATCH_DETAIL, breaker=breaker, match_id=match_id)        
            return data
        except CircuitBreakerError:
            return None

    def fetch_lineups(self, match_id: int, breaker: Optional[CircuitBreaker] = None) -> Optional[Dict]:
        """Wrapper để lấy đội hình."""
        try:
            return self._make_request(SofaScoreEndpoints.MATCH_LINEUPS, breaker=breaker, match_id=match_id)
        except CircuitBreakerError:
            return None

    def fetch_statistics(self, match_id: int, breaker: Optional[CircuitBreaker] = None) -> Optional[Dict]:
        """Wrapper để lấy thống kê."""
        try:
            return self._make_request(SofaScoreEndpoints.MATCH_STATISTICS, breaker=breaker, match_id=match_id)
        except CircuitBreakerError:
            return None

    def fetch_incidents(self, match_id: int, breaker: Optional[CircuitBreaker] = None) -> Optional[Dict]:
        """Wrapper để lấy các sự kiện (bàn thắng, thẻ phạt, etc.)."""
        try:
            # Gọi hàm _make_request với endpoint MATCH_INCIDENTS
            data = self._make_request(
                SofaScoreEndpoints.MATCH_INCIDENTS, 
                breaker=breaker, 
                match_id=match_id
            )
            # Dữ liệu sự kiện nằm trong key 'incidents'
            return data.get("incidents") if data else None
        except CircuitBreakerError:
            return None

    def fetch_paginated_events(self, endpoint: SofaScoreEndpoints, breaker: Optional[CircuitBreaker] = None, **kwargs) -> List[Dict]:
        """Alias for fetch_paginated_data to match orchestrator expectations."""
        items, _ = self.fetch_paginated_data(endpoint, breaker=breaker, **kwargs)
        return items

    def close(self):
        """Đóng session khi hoàn tất."""
        self.session.close()
        logger.info("SofaScoreClient session closed.")