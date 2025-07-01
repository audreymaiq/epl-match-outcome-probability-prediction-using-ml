# ai-engine\elt_pipeline\run_sofascore.py

"""
Trình điều phối (Orchestrator) Tối ưu cho SofaScore Data Pipeline.

Kết hợp kiến trúc xử lý song song (tốc độ, khả năng phục hồi) với các tính năng
vận hành chuyên nghiệp (caching, session rotation, graceful shutdown).

Kiến trúc:
- Giao diện dòng lệnh (CLI) mạnh mẽ.
- Xử lý đồng thời (multi-threading) cho từng trận đấu.
- HTTP Caching để tăng tốc trong quá trình phát triển và chạy lại.
- Session Rotation để tăng cường khả năng chống bị chặn.
- Circuit Breaker cho từng loại endpoint để cách ly lỗi.
- Báo cáo và logging chi tiết, với mã thoát (exit code) chuẩn.
"""

import argparse
import logging
import sys
import time
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple
import threading
import gc

# --- 1. THIẾT LẬP IMPORT VÀ XỬ LÝ LỖI SỚM ---
try:
    from pybreaker import CircuitBreaker, CircuitBreakerError
    from tqdm import tqdm
    import requests_cache
    
    # --- Import các thành phần cốt lõi của pipeline ---
    from config.env_loader import load_environment
    from utils.logging_config import setup_logging, teardown_logging
    from config.settings import get_config, ConfigManager
    from utils.db_connector import DatabaseConnector
    from elt_pipeline.extract.sofascore_extractor import SofaScoreExtractor
    from elt_pipeline.extract.sofascore_endpoints import SofaScoreEndpoints, EndpointCategory
    from elt_pipeline.transform.sofascore_transformer import SofaScoreTransformer
    from elt_pipeline.load.sofascore_loader import SofaScoreLoader, LoaderError
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}\n"
          f"Please ensure project dependencies are installed and PYTHONPATH is set.", file=sys.stderr)
    sys.exit(1)

# Tải môi trường ngay khi script được import
try:
    load_environment()
except Exception as e:
    print(f"CRITICAL: Failed to load environment: {e}", file=sys.stderr)
    sys.exit(1)

# --- 2. CÁC HẰNG SỐ VÀ CẤU HÌNH CHO ORCHESTRATOR ---
DEFAULT_WORKERS = 8
CIRCUIT_BREAKER_FAIL_MAX = 5
CIRCUIT_BREAKER_TIMEOUT = 300 # 5 phút

# Cờ toàn cục để xử lý tín hiệu thoát
SHUTDOWN_EVENT = threading.Event()

# --- 3. CÁC HÀM TIỆN ÍCH VÀ THIẾT LẬP ---
def parse_arguments() -> argparse.Namespace:
    """Phân tích các tham số từ dòng lệnh (CLI)."""
    parser = argparse.ArgumentParser(
        description="SofaScore Data Pipeline Orchestrator (Optimized Version).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--seasons", nargs="+", type=int,
        help="List of season start years to process (e.g., 2022 2023). Defaults to config."
    )
    parser.add_argument(
        "--full-history", action="store_true",
        help="Run for all supported seasons defined in the configuration."
    )
    parser.add_argument(
        "--workers", type=int, default=DEFAULT_WORKERS,
        help="Number of concurrent processing threads."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run Extract & Transform without loading data into the database."
    )
    parser.add_argument(
        "--log-level", default=None, choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override a log level from the environment variables."
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Disable HTTP request caching for this run."
    )
    return parser.parse_args()


def setup_http_caching(config: ConfigManager, no_cache_flag: bool):
    """Kích hoạt caching cho requests nếu được cấu hình."""
    if no_cache_flag or not config.scraping.enable_cache:
        logging.getLogger(__name__).info("HTTP Caching is DISABLED for this run.")
        return
        
    try:
        requests_cache.install_cache(
            cache_name=config.scraping.cache_dir,
            backend='sqlite',
            expire_after=config.scraping.cache_ttl,
            allowable_methods=['GET']
        )
        logging.getLogger(__name__).info(
            f"HTTP Caching ENABLED. TTL: {config.scraping.cache_ttl}s. Cache: {config.scraping.cache_dir}.sqlite"
        )
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to enable requests-cache: {e}. Continuing without cache.")


def handle_graceful_shutdown(signum, frame):
    """Xử lý tín hiệu Ctrl+C để ra lệnh cho các luồng dừng lại một cách an toàn."""
    logging.getLogger(__name__).warning("Shutdown signal received. Signalling all threads to stop...")
    SHUTDOWN_EVENT.set()


# --- 4. LỚP QUẢN LÝ TÀI NGUYÊN (Resource Manager) ---
class ResourceManager:
    """
    Quản lý các tài nguyên chia sẻ như Extractor, Session và Circuit Breaker
    một cách thread-safe.
    """
    def __init__(self, config: ConfigManager):
        self.config = config
        self._extractor: Optional[SofaScoreExtractor] = None
        self._requests_since_rotation = 0
        self._lock = threading.Lock()
        
        # Tạo Circuit Breaker cho từng loại endpoint
        self.breakers: Dict[EndpointCategory, CircuitBreaker] = {
            category: CircuitBreaker(
                fail_max=self.config.sofascore.circuit_breaker_threshold,
                reset_timeout=self.config.sofascore.circuit_breaker_timeout,
                name=f"{category.value}_breaker"
            )
            for category in EndpointCategory
        }
        logging.getLogger(__name__).info("Circuit Breakers initialized for all categories.")

    def get_extractor(self) -> SofaScoreExtractor:
        """
        Quản lý việc tạo và xoay vòng (rotate) Extractor/Session.
        Đây là trái tim của việc chống bị chặn.
        """
        with self._lock:
            self._requests_since_rotation += 1
            rotation_interval = self.config.sofascore.session_rotation_interval
            
            if (self._extractor is None or
                (rotation_interval > 0 and self._requests_since_rotation > rotation_interval)):
                
                if self._extractor:
                    logging.getLogger(__name__).info(
                        f"Rotating session after {self._requests_since_rotation-1} requests."
                    )
                    self._extractor.close()

                self._extractor = SofaScoreExtractor(self.config.sofascore, self.config.scraping)
                self._requests_since_rotation = 1
            
            return self._extractor
            
    def get_breaker(self, endpoint: SofaScoreEndpoints) -> CircuitBreaker:
        """Lấy Circuit Breaker phù hợp cho một endpoint."""
        # Tạm thời dùng một breaker chung, có thể mở rộng logic này
        # Dựa trên `get_endpoint_category(endpoint)` nếu cần chính sách khác nhau.
        return self.breakers[EndpointCategory.STANDARD]

    def close(self):
        """Đóng các tài nguyên."""
        with self._lock:
            if self._extractor:
                self._extractor.close()
                self._extractor = None


# --- 5. ĐƠN VỊ CÔNG VIỆC (Work Unit) ---
def fetch_and_process_match(
    match_summary: Dict[str, Any],
    resource_manager: ResourceManager,
    transformer: SofaScoreTransformer,
    dry_run: bool = False
) -> Tuple[bool, Optional[int]]:
    """
    Hàm thực thi cho một luồng (worker): xử lý một trận đấu hoàn chỉnh (E-T-L).
    Trả về (thành công_hay_không, external_id_của_trận_đấu).
    """
    logger = logging.getLogger(__name__)
    match_id = match_summary.get('id')
    if not match_id:
        logger.warning("Match summary is missing 'id'. Skipping.", extra={"summary": match_summary})
        return False, None
    
    # Kiểm tra tín hiệu thoát trước khi bắt đầu
    if SHUTDOWN_EVENT.is_set():
        logger.info(f"Shutdown signaled. Skipping match {match_id}.")
        return False, match_id

    try:
        # --- Giai đoạn Extract ---
        extractor = resource_manager.get_extractor()
        breaker = resource_manager.get_breaker(SofaScoreEndpoints.MATCH_DETAIL)
        
        # Dữ liệu chi tiết và sự kiện được fetch ở đây
        raw_events = extractor.fetch_incidents(match_id, breaker=breaker)

        # --- Giai đoạn Transform ---
        parsed_match = transformer.transform_match_and_events(
            raw_summary=match_summary,
            raw_events=raw_events
        )
        if not parsed_match:
            logger.error(f"Transformation failed for match_id={match_id}.")
            return False, match_id

        # --- Giai đoạn Load ---
        if dry_run:
            logger.info(f"[DRY-RUN] Would load match: {parsed_match.home_team.name} vs {parsed_match.away_team.name}")
            return True, match_id
        
        # Tạo session DB riêng cho mỗi luồng để đảm bảo thread-safety
        with DatabaseConnector.session_scope() as session:
            loader = SofaScoreLoader(session)
            loaded_id = loader.load_full_match_data(parsed_match)
        
        if not loaded_id:
            logger.error(f"Loading failed for match_id={match_id}.")
            return False, match_id

        return True, match_id

    except CircuitBreakerError as e:
        logger.error(f"Circuit breaker is open for match_id={match_id}. Aborting. Error: {e}")
        return False, match_id
    except LoaderError as e:
        logger.error(f"A loader error occurred for match_id={match_id}: {e}", exc_info=True)
        return False, match_id
    except Exception as e:
        # Kiểm tra lần nữa nếu lỗi là do người dùng ra lệnh thoát
        if SHUTDOWN_EVENT.is_set():
            logger.warning(f"Task for match {match_id} cancelled due to shutdown signal.")
        else:
            logger.error(f"An unexpected error occurred for match_id={match_id}: {e}", exc_info=True)
        return False, match_id


# --- 6. HÀM ĐIỀU PHỐI CHÍNH ---
def run_orchestrator(args: argparse.Namespace) -> int:
    """Hàm chính điều phối toàn bộ pipeline, trả về mã thoát."""
    logger = logging.getLogger(__name__)
    start_time = time.time()
    resource_manager = None

    try:
        # 1. Khởi tạo các thành phần cốt lõi
        config: ConfigManager = get_config()
        setup_http_caching(config, args.no_cache)
        
        if not DatabaseConnector.check_connection():
            logger.critical("Database connection failed. Aborting pipeline.")
            return 1

        resource_manager = ResourceManager(config)
        transformer = SofaScoreTransformer()
        
        # 2. Xác định các mùa giải mục tiêu
        # ... logic này giữ nguyên như phiên bản của tôi ...
        target_seasons = []
        all_seasons_map = {s[0]: (s[1], s[2]) for s in config.get_target_seasons_with_ids()}
        if args.seasons:
            for year in args.seasons:
                if year in all_seasons_map:
                    name, sid = all_seasons_map[year]
                    target_seasons.append((year, name, sid))
                else:
                    logger.warning(f"Season year {year} not found. Skipping.")
        elif args.full_history:
            target_seasons = config.get_target_seasons_with_ids()
        else:
            target_seasons = config.get_target_seasons_with_ids()

        if not target_seasons:
            logger.warning("No target seasons found to process.")
            return 0

        logger.info(f"Target seasons to process: {[s[1] for s in target_seasons]}")
        
        # 3. Thu thập danh sách tất cả các trận đấu
        all_match_summaries = []
        extractor = resource_manager.get_extractor() # Lấy extractor ban đầu
        breaker = resource_manager.get_breaker(SofaScoreEndpoints.SEASON_MATCHES_LAST)
        
        for _, season_name, season_id in target_seasons:
            if SHUTDOWN_EVENT.is_set(): break
            logger.info(f"Fetching match list for season: {season_name}...")
            matches, _ = extractor.fetch_paginated_data(
                SofaScoreEndpoints.SEASON_MATCHES_LAST,
                breaker=breaker,
                tournament_id=config.sofascore.premier_league_id,
                season_id=season_id
            )
            all_match_summaries.extend(matches)
        
        # Xóa các trận đấu trùng lặp
        all_match_summaries = list({m['id']: m for m in all_match_summaries}.values())

        if not all_match_summaries:
            logger.error("No matches found for the target seasons.")
            return 1
        
        total_matches = len(all_match_summaries)
        logger.info(f"Total unique matches to process across all seasons: {total_matches}")

        # 4. Xử lý đồng thời
        results = {"success": 0, "failed": 0, "failed_ids": []}
        
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_match = {
                executor.submit(
                    fetch_and_process_match,
                    match, resource_manager, transformer, args.dry_run
                ): match.get('id')
                for match in all_match_summaries
            }
            
            progress_bar = tqdm(as_completed(future_to_match), total=total_matches, desc="Processing Matches", unit="match")
            for future in progress_bar:
                if SHUTDOWN_EVENT.is_set():
                    # Cố gắng cancel các task còn lại
                    future.cancel()
                    continue

                match_id = future_to_match[future]
                try:
                    is_success, processed_id = future.result()
                    if is_success:
                        results["success"] += 1
                    else:
                        results["failed"] += 1
                        results["failed_ids"].append(processed_id or match_id)
                except Exception:
                    logger.error(f"A future task raised an exception for match_id={match_id}", exc_info=True)
                    results["failed"] += 1
                    results["failed_ids"].append(match_id)
        
        # 5. Báo cáo kết quả
        duration = time.time() - start_time
        logger.info("=" * 60)
        logger.info("🏁 SofaScore Data Pipeline Finished")
        logger.info(f"Total time: {duration:.2f} seconds")
        logger.info(f"Total matches scheduled: {total_matches}")
        logger.info(f"  - Successful: {results['success']}")
        logger.info(f"  - Failed: {results['failed']}")
        if results['failed'] > 0:
            logger.warning(f"Failed match IDs (check logs for details): {results['failed_ids'][:20]}") # Giới hạn số ID in ra
        
        return 0 if results['failed'] == 0 else 1

    except KeyboardInterrupt:
        logger.warning("\nPipeline orchestration interrupted by user. Final cleanup initiated.")
        return 130
    except Exception as e:
        logger.critical("A fatal unhandled error occurred in orchestrator.", exc_info=True)
        return 1
    finally:
        # Dọn dẹp tài nguyên
        if resource_manager:
            resource_manager.close()
        if requests_cache.is_installed():
            requests_cache.uninstall_cache()
        teardown_logging()
        gc.collect()


# --- 7. ENTRY POINT ---
def main():
    """Entry point chính của ứng dụng."""
    args = parse_arguments()
    setup_logging(log_level=args.log_level)
    
    # Đăng ký xử lý tín hiệu thoát an toàn
    signal.signal(signal.SIGINT, handle_graceful_shutdown)
    signal.signal(signal.SIGTERM, handle_graceful_shutdown)
    
    exit_code = run_orchestrator(args)
    
    logging.getLogger(__name__).info(f"Pipeline exiting with code {exit_code}.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()