# elt_pipeline\extract\sofascore_extractor.py

"""
SofaScore ETL Pipeline: Client: Chỉ fetch dữ liệu thô từ API.
"""

import time
import logging
from typing import List, Dict, Any, Optional
import requests

# Import các thành phần từ kiến trúc đã xây dựng
from config.settings import get_config, SofascoreSettings, ScrapingSettings
from elt_pipeline.extract.sofascore_endpoints import (
    SofaScoreEndpoints, build_url, get_headers, get_timeout_settings,
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
        self.session = requests.Session()

    def _make_request(self, endpoint: SofaScoreEndpoints, params: Optional[Dict] = None, **kwargs) -> Optional[Any]:
        """
        Phương thức private để thực hiện request với retry, delay và config động.
        """
        validate_endpoint_params(endpoint, **kwargs)
        url = build_url(endpoint, params, **kwargs)
        
        # Lấy cấu hình ĐỘNG cho từng endpoint cụ thể
        headers = get_headers(endpoint)
        timeout = get_timeout_settings(endpoint)
        delay_seconds = 1 / get_rate_limit_per_second(endpoint)
        max_retries = self.scraping_config.max_retries
        backoff_factor = self.scraping_config.backoff_factor

        for attempt in range(max_retries):
            try:
                time.sleep(delay_seconds * (backoff_factor ** attempt))
                
                logger.debug("Making request", extra={
                    "url": url, "attempt": attempt + 1, "timeout": timeout
                })

                response = self.session.get(url, headers=headers, timeout=timeout)
                
                if response.status_code == 404:
                    if endpoint == SofaScoreEndpoints.SEASON_MATCHES and 'page' in kwargs:
                        logger.info("End of pagination reached", extra={"url": url})
                        return None  # Kết thúc pagination bình thường
                    else:
                        logger.warning("Resource not found", extra={"url": url})
                        return None  # Resource không tồn tại

                response.raise_for_status() # Ném exception cho các mã lỗi 4xx, 5xx khác
                return response.json()

            except requests.exceptions.RequestException as e:
                logger.warning("Request failed", extra={
                    "url": url, "attempt": attempt + 1, "max_retries": max_retries, "error": str(e)
                })
                if attempt == max_retries - 1:
                    logger.error("Max retries exceeded for request.", extra={"url": url})
                    return None
        return None
    
    def fetch_paginated_data(self, endpoint: SofaScoreEndpoints, **kwargs) -> List[Dict]:
        """Fetch dữ liệu từ các endpoint có phân trang."""
        all_items = []
        page = 0
        while True:
            page += 1
            kwargs['page'] = page
            
            data = self._make_request(endpoint, **kwargs)
            
            # API trả về 'events' cho danh sách trận đấu
            items = data.get("events", []) if data else []

            if not isinstance(items, list) or not items:
                logger.info("No more items found or response is not a list, stopping pagination.", extra={"endpoint": endpoint.name, "last_page": page-1})
                break
            
            all_items.extend(items)
            
        return all_items

    def fetch_match_detail(self, match_id: int) -> Optional[Dict]:
        """Wrapper đơn giản để lấy chi tiết trận đấu."""
        data = self._make_request(SofaScoreEndpoints.MATCH_DETAIL, match_id=match_id)
        return data.get("event") if data else None

    def fetch_lineups(self, match_id: int) -> Optional[Dict]:
        """Wrapper để lấy đội hình."""
        return self._make_request(SofaScoreEndpoints.MATCH_LINEUPS, match_id=match_id)

    def fetch_statistics(self, match_id: int) -> Optional[Dict]:
        """Wrapper để lấy thống kê."""
        return self._make_request(SofaScoreEndpoints.MATCH_STATISTICS, match_id=match_id)

    def fetch_paginated_events(self, endpoint: SofaScoreEndpoints, **kwargs) -> List[Dict]:
        """Alias for fetch_paginated_data to match orchestrator expectations."""
        return self.fetch_paginated_data(endpoint, **kwargs)

    def close(self):
        """Đóng session khi hoàn tất."""
        self.session.close()
        logger.info("SofaScoreClient session closed.")