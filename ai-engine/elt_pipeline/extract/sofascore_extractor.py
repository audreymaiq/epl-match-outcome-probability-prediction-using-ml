# elt_pipeline\extract\sofascore_extractor.py

"""
SofaScore ETL Pipeline: Client: Chỉ fetch dữ liệu thô từ API.
"""

import time
import logging
from typing import List, Dict, Any, Optional
from curl_cffi.requests import Session, RequestsError
import pybreaker

# Import các thành phần từ kiến trúc đã xây dựng
from config.settings import SofascoreSettings, ScrapingSettings
from elt_pipeline.extract.sofascore_endpoints import (
    SofaScoreEndpoints, build_url, get_headers,
    get_rate_limit_per_second, validate_endpoint_params
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
        breaker: Optional[pybreaker.CircuitBreaker] = None,
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
        timeout_val = self.scraping_config.request_timeout
        max_retries = self.scraping_config.max_retries
        backoff_factor = self.scraping_config.backoff_factor

        for attempt in range(max_retries):
            try:
                # Hàm thực thi request thực tế
                def _execute_get():
                    random_delay = self.scraping_config.get_random_delay()
                    sleep_duration = random_delay * (backoff_factor ** attempt)
                    time.sleep(sleep_duration)

                    proxy = self.scraping_config.get_random_proxy()
                    proxies = {"http": proxy, "https": proxy} if proxy else None

                    log_extra = {
                        "url": url, "attempt": attempt + 1, "timeout": timeout_val,
                        "proxy": "Yes" if proxy else "No", "sleep": round(sleep_duration, 2)
                    }
                    logger.debug("Making request", extra=log_extra)

                    response = self.session.get(url, headers=headers, timeout=timeout_val, proxies=proxies)

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

            except pybreaker.CircuitBreakerError as e:
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
    
    def fetch_paginated_data(self, endpoint: SofaScoreEndpoints, breaker: Optional[Any] = None, **kwargs) -> tuple[List[Dict], int]:
        """Fetch dữ liệu từ các endpoint có phân trang và trả về số request đã thực hiện."""
        all_items = []
        page = 0
        requests_made = 0
        while True:
            page += 1
            kwargs['page'] = page
            
            data = self._make_request(endpoint, breaker=breaker, **kwargs)
            requests_made += 1 # Đếm mỗi lần gọi _make_request

            items = data.get("events", []) if data else []

            if not isinstance(items, list) or not items:
                logger.info("No more items found...", extra={"endpoint": endpoint.name, "last_page": page-1})
                break
            
            all_items.extend(items)
            
        return all_items, requests_made

    def fetch_match_detail(self, match_id: int, breaker: Optional[Any] = None) -> Optional[Dict]:
        """Wrapper đơn giản để lấy chi tiết trận đấu."""
        data = self._make_request(SofaScoreEndpoints.MATCH_DETAIL, breaker=breaker, match_id=match_id)        
        return data.get("event") if data else None

    def fetch_lineups(self, match_id: int, breaker: Optional[Any] = None) -> Optional[Dict]:
        """Wrapper để lấy đội hình."""
        return self._make_request(SofaScoreEndpoints.MATCH_LINEUPS, breaker=breaker, match_id=match_id)

    def fetch_statistics(self, match_id: int, breaker: Optional[Any] = None) -> Optional[Dict]:
        """Wrapper để lấy thống kê."""
        return self._make_request(SofaScoreEndpoints.MATCH_STATISTICS, breaker=breaker, match_id=match_id)

    def fetch_paginated_events(self, endpoint: SofaScoreEndpoints, breaker: Optional[Any] = None, **kwargs) -> List[Dict]:
        """Alias for fetch_paginated_data to match orchestrator expectations."""
        return self.fetch_paginated_data(endpoint, breaker=breaker, **kwargs)

    def close(self):
        """Đóng session khi hoàn tất."""
        self.session.close()
        logger.info("SofaScoreClient session closed.")