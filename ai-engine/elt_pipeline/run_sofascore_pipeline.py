# elt_pipeline/run_sofascore_pipeline.py
# PHIÊN BẢN HOÀN CHỈNH ĐÃ SỬA LỖI VÀ TỐI ƯU HÓA

import sys
import signal
import logging
import argparse
import threading
import gc
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple, TypedDict
from contextlib import contextmanager
import pybreaker
import requests_cache
import time

# --- 1. THIẾT LẬP IMPORT VÀ XỬ LÝ LỖI SỚM ---
try:
    from utils.logging_config import setup_logging
    from config.settings import get_config, ConfigManager
    from utils.db_connector import DatabaseConnector

    from elt_pipeline.extract.sofascore_extractor import SofaScoreExtractor
    from elt_pipeline.extract.sofascore_endpoints import SofaScoreEndpoints
    from elt_pipeline.transform.sofascore_transformer import SofaScoreTransformer
    from elt_pipeline.transform.data_structures import ParsedMatch
    from elt_pipeline.load.sofascore_loader import SofaScoreLoader
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}\n"
        f"Please ensure your project structure is correct and PYTHONPATH is set.\n"
        f"Run 'pip install -e .' from the project root if you haven't already.", file=sys.stderr)
    sys.exit(1)

# Khởi tạo logger sau khi đã import thành công logging_config
logger = logging.getLogger(__name__)

# --- 2. TYPE DEFINITIONS ---
class ProcessResult(TypedDict):
    """Định nghĩa cấu trúc kết quả xử lý mùa giải"""
    total: int
    success: int
    failed: int
    failed_matches: List[str]
    season_name: str
    duration_seconds: float

class PipelineResult(TypedDict):
    """Định nghĩa cấu trúc kết quả toàn bộ pipeline"""
    success: bool
    total_seasons: int
    successful_seasons: int
    total_matches: int
    successful_matches: int
    duration_seconds: float
    season_results: List[ProcessResult]

# --- 3. LỚP ĐIỀU PHỐI (ORCHESTRATOR) - ĐÃ SỬA LỖI VÀ TỐI ƯU HÓA ---
class SofaScoreETLOrchestrator:
    """
    Điều phối toàn bộ quy trình ETL với kiến trúc xử lý hàng loạt (Bulk Processing).
    Quản lý Session Rotation và Circuit Breaker một cách hiệu quả và thread-safe.
    """

    def __init__(self, config: ConfigManager, transformer: SofaScoreTransformer):
        self.config = config
        self.transformer = transformer
        self.extractor: Optional[SofaScoreExtractor] = None
        self.requests_since_rotation = 0
        self._lock = threading.Lock()  # Thread safety cho session rotation
        
        # Validate config structure
        self._validate_config()
        
        # Khởi tạo Circuit Breaker từ cấu hình một lần duy nhất
        self.breaker = pybreaker.CircuitBreaker(
            fail_max=self.config.sofascore.circuit_breaker_threshold,
            reset_timeout=self.config.sofascore.circuit_breaker_timeout,
        )
        logger.info(
            "Circuit Breaker initialized: fail_max=%d, reset_timeout=%ds",
            self.breaker.fail_max, self.breaker.reset_timeout
        )

    def _validate_config(self) -> None:
        """Validate cấu trúc config để tránh AttributeError runtime"""
        required_sofascore_attrs = [
            'circuit_breaker_threshold', 'circuit_breaker_timeout', 
            'session_rotation_interval', 'premier_league_id'
        ]
        required_scraping_attrs = [
            'delay_between_requests', 'enable_cache', 'cache_dir', 'cache_ttl'
        ]
        
        for attr in required_sofascore_attrs:
            if not hasattr(self.config.sofascore, attr):
                raise ValueError(f"Missing required config: sofascore.{attr}")
                
        for attr in required_scraping_attrs:
            if not hasattr(self.config.scraping, attr):
                raise ValueError(f"Missing required config: scraping.{attr}")

    def _get_extractor(self) -> SofaScoreExtractor:
        """
        Quản lý việc tạo và xoay vòng (rotate) Extractor/Session với thread safety.
        """
        with self._lock:
            rotation_interval = self.config.sofascore.session_rotation_interval
            
            if (self.extractor is None or 
                (rotation_interval > 0 and self.requests_since_rotation >= rotation_interval)):
                
                if self.extractor:
                    logger.info(
                        "Rotating session after %d requests (interval: %d).",
                        self.requests_since_rotation, rotation_interval
                    )
                    self.extractor.close()

                self.extractor = SofaScoreExtractor(self.config.sofascore, self.config.scraping)
                self.requests_since_rotation = 0
            
            return self.extractor

    @contextmanager
    def _managed_extractor(self):
        """Context manager để đảm bảo extractor được đóng đúng cách"""
        extractor = None
        try:
            extractor = self._get_extractor()
            yield extractor
        except Exception:
            # Nếu có lỗi, đóng extractor hiện tại để tạo mới lần sau
            if extractor and extractor == self.extractor:
                self.extractor = None
            raise
    
    def process_season(self, season_id: int, season_name: str, tournament_id: int) -> ProcessResult:
        """
        Xử lý toàn bộ một mùa giải theo quy trình Extract-All, Transform-All, Load-All.
        """
        start_time = datetime.now()
        logger.info("--- Starting Bulk ETL for season: %s (ID: %d) ---", season_name, season_id)
        
        # Initialize variables để tránh UnboundLocalError
        raw_summaries = []
        full_raw_matches = []
        parsed_matches = []
        
        try:
            # === PHASE 1: EXTRACT ALL RAW DATA ===
            with self._managed_extractor() as extractor:
                # 1.1: Lấy danh sách tóm tắt tất cả các trận đấu
                raw_summaries, req_count = extractor.fetch_paginated_data(
                    SofaScoreEndpoints.SEASON_MATCHES_LAST,
                    breaker=self.breaker,
                    tournament_id=tournament_id,
                    season_id=season_id
                )
                
                with self._lock:
                    self.requests_since_rotation += req_count
                
                if not raw_summaries:
                    logger.warning("No match summaries found for season %s. Skipping.", season_name)
                    return self._create_empty_result(season_name, start_time)

                # 1.2: Lấy dữ liệu chi tiết và sự kiện cho từng trận đấu
                total_matches_to_fetch = len(raw_summaries)
                logger.info("Extracted %d summaries. Now fetching details and events...", total_matches_to_fetch)

                for i, summary in enumerate(raw_summaries):
                    ext_match_id = summary.get("id")
                    if not ext_match_id:
                        logger.warning("Match summary missing ID, skipping")
                        continue
                    
                    log_extra = {"ext_id": ext_match_id, "progress": f"{i+1}/{total_matches_to_fetch}"}
                    logger.debug("Fetching full data for match", extra=log_extra)
                    
                    try:
                        # Lấy detail và events
                        with self._managed_extractor() as current_extractor:
                            detail = current_extractor.fetch_match_detail(int(ext_match_id), breaker=self.breaker)
                            with self._lock:
                                self.requests_since_rotation += 1
                            
                            events = current_extractor.fetch_incidents(int(ext_match_id), breaker=self.breaker)
                            with self._lock:
                                self.requests_since_rotation += 1
                        
                        # Chỉ thêm vào danh sách xử lý nếu có dữ liệu detail
                        if detail:
                            full_raw_matches.append({
                                "summary": summary,
                                "detail": detail,
                                "events": events or []
                            })
                        else:
                            logger.warning("No detail data for match %s", ext_match_id)
                    
                    except (ConnectionError, TimeoutError) as e:
                        logger.error("Network error fetching match %s: %s", ext_match_id, e)
                        continue
                    except Exception as e:
                        logger.error("Unexpected error fetching match %s: %s", ext_match_id, e)
                        continue
                    
                    # Rate limiting
                    if self.config.scraping.delay_between_requests > 0:
                        time.sleep(self.config.scraping.delay_between_requests)

        except pybreaker.CircuitBreakerError as e:
            logger.critical("Circuit Breaker is open during EXTRACT phase. Skipping season %s. Error: %s", 
                        season_name, e)
            return self._create_failed_result(season_name, len(raw_summaries), start_time)
        except KeyboardInterrupt:
            logger.warning("Season processing interrupted by user")
            raise
        except Exception as e:
            logger.error("Failed to extract full season data for %s. Error: %s", season_name, e, exc_info=True)
            return self._create_failed_result(season_name, len(raw_summaries), start_time)
        
        # === PHASE 2: TRANSFORM ALL RAW DATA ===
        logger.info("Extract phase complete. Now transforming %d matches...", len(full_raw_matches))
        
        try:
            for raw_data in full_raw_matches:
                try:
                    parsed_match = self.transformer.transform_match_and_events(
                        raw_summary=raw_data["summary"],
                        raw_detail=raw_data["detail"],
                        raw_events=raw_data["events"]
                    )
                    if parsed_match:
                        parsed_matches.append(parsed_match)
                    else:
                        logger.warning("A match failed to transform and will be skipped.", 
                                    extra={"ext_id": raw_data.get("summary", {}).get("id")})
                except Exception as e:
                    ext_id = raw_data.get("summary", {}).get("id", "unknown")
                    logger.error("Error transforming match %s: %s", ext_id, e)
                    continue
            
            # Clear raw data để giải phóng memory
            full_raw_matches.clear()
            gc.collect()
            
        except Exception as e:
            logger.error("Critical error during transform phase: %s", e, exc_info=True)
            return self._create_failed_result(season_name, len(raw_summaries), start_time)
        
        # === PHASE 3: LOAD ALL TRANSFORMED DATA ===
        logger.info("Transform phase complete. Now loading %d matches into the database...", len(parsed_matches))
        
        if not parsed_matches:
            logger.warning("No matches to load after transformation. Finishing season.")
            return ProcessResult(
                total=len(raw_summaries),
                success=0,
                failed=len(raw_summaries),
                failed_matches=[],
                season_name=season_name,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
        
        try:
            with DatabaseConnector.session_scope() as session:
                loader = SofaScoreLoader(session)
                load_results = loader.bulk_load_matches(parsed_matches)
            
            # Clear parsed data để giải phóng memory
            parsed_matches.clear()
            gc.collect()
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info("--- Finished ETL for season: %s. Success: %d, Failed: %d, Duration: %.2fs ---",
                    season_name, load_results['success'], load_results['failed'], duration)
            
            return ProcessResult(
                total=load_results.get('total', len(raw_summaries)),
                success=load_results['success'],
                failed=load_results['failed'],
                failed_matches=load_results.get('failed_matches', []),
                season_name=season_name,
                duration_seconds=duration
            )

        except Exception as e:
            logger.critical("A critical error occurred during the LOAD phase for season %s. Transaction was rolled back.", 
                        season_name, exc_info=True)
            return self._create_failed_result(season_name, len(parsed_matches), start_time)

    def _create_empty_result(self, season_name: str, start_time: datetime) -> ProcessResult:
        """Tạo kết quả rỗng cho mùa giải không có dữ liệu"""
        return ProcessResult(
            total=0,
            success=0,
            failed=0,
            failed_matches=[],
            season_name=season_name,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )

    def _create_failed_result(self, season_name: str, total_count: int, start_time: datetime) -> ProcessResult:
        """Tạo kết quả thất bại cho mùa giải gặp lỗi"""
        return ProcessResult(
            total=total_count,
            success=0,
            failed=total_count,
            failed_matches=[],
            season_name=season_name,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )

    def close(self):
        """Dọn dẹp tài nguyên khi kết thúc."""
        with self._lock:
            if self.extractor:
                try:
                    self.extractor.close()
                except Exception as e:
                    logger.warning("Error closing extractor: %s", e)
                finally:
                    self.extractor = None

# --- 4. CÁC HÀM HỖ TRỢ VÀ ENTRY POINT ---
def handle_graceful_shutdown(signum, frame):
    """Xử lý tín hiệu Ctrl+C để tắt chương trình một cách an toàn."""
    logger.warning("Shutdown signal received. Attempting graceful exit...")
    raise KeyboardInterrupt 

def setup_cache(config: ConfigManager) -> bool:
    """Kích hoạt caching cho requests nếu được cấu hình."""
    if not config.scraping.enable_cache:
        logger.info("HTTP Caching is DISABLED.")
        return True
        
    try:
        requests_cache.install_cache(
            cache_name=config.scraping.cache_dir,
            backend='sqlite',
            expire_after=config.scraping.cache_ttl,
            allowable_methods=['GET']
        )
        logger.info("HTTP Caching is ENABLED. TTL: %ds. Cache file: %s.sqlite", 
                config.scraping.cache_ttl, config.scraping.cache_dir)
        return True
    except Exception as e:
        logger.error("Failed to enable requests-cache: %s", e)
        return False

def cleanup_resources():
    """Hàm dọn dẹp tài nguyên tập trung."""
    try:
        if requests_cache.is_installed():
            requests_cache.uninstall_cache()
            logger.info("HTTP Caching uninstalled.")
    except Exception as e:
        logger.warning("Failed to uninstall cache: %s", e)
    
    try:
        DatabaseConnector.close_all_connections()
        logger.info("Database connections closed.")
    except Exception as e:
        logger.warning("Failed to close database connections: %s", e)

def run_pipeline(specific_season_names: Optional[List[str]] = None) -> PipelineResult:
    """Hàm điều phối chính, chạy toàn bộ pipeline."""
    start_time = datetime.now()
    pipeline_result = PipelineResult(
        success=False,
        total_seasons=0,
        successful_seasons=0,
        total_matches=0,
        successful_matches=0,
        duration_seconds=0.0,
        season_results=[]
    )
    
    orchestrator = None
    try:
        config = get_config()
        
        # Thiết lập cache trước khi thực hiện bất kỳ request nào
        if not setup_cache(config):
            logger.error("Failed to setup cache. Continuing without cache.")
        
        # Kiểm tra kết nối DB sớm để "fail-fast"
        if not DatabaseConnector.check_connection():
            logger.critical("Database connection failed. Aborting pipeline.")
            return pipeline_result

        # Khởi tạo các thành phần cốt lõi
        transformer = SofaScoreTransformer(api_type='sofascore')
        orchestrator = SofaScoreETLOrchestrator(config, transformer)
        
        # Lấy và lọc các mùa giải cần xử lý
        all_seasons_from_config = config.get_target_seasons_with_ids()
        seasons_to_process: List[Tuple[int, str, int]] = []
        
        if specific_season_names:
            specific_set = set(specific_season_names)
            seasons_to_process = [s for s in all_seasons_from_config if s[1] in specific_set]
            if not seasons_to_process:
                logger.error("None of the specified seasons %s are configured to be fetched.", specific_season_names)
                return pipeline_result
        else:
            seasons_to_process = all_seasons_from_config

        if not seasons_to_process:
            logger.warning("No seasons configured to process.")
            pipeline_result['success'] = True  # Không có gì để xử lý cũng coi như thành công
            return pipeline_result

        pipeline_result['total_seasons'] = len(seasons_to_process)
        logger.info("Pipeline will process %d season(s): %s", 
                len(seasons_to_process), [s[1] for s in seasons_to_process])
        
        # Chạy pipeline cho từng mùa giải và tổng hợp kết quả
        for _, season_name, season_id in seasons_to_process:
            try:
                season_result = orchestrator.process_season(
                    season_id=season_id,
                    season_name=season_name,
                    tournament_id=config.sofascore.premier_league_id
                )
                
                pipeline_result['season_results'].append(season_result)
                pipeline_result['total_matches'] += season_result['total']
                pipeline_result['successful_matches'] += season_result['success']
                
                if season_result['success'] > 0 or season_result['total'] == 0:
                    pipeline_result['successful_seasons'] += 1
                    
            except KeyboardInterrupt:
                logger.warning("Pipeline interrupted during season %s", season_name)
                raise
            except Exception as e:
                logger.error("Critical error processing season %s: %s", season_name, e, exc_info=True)
                # Tạo failed result cho season này
                failed_result = ProcessResult(
                    total=0,
                    success=0,
                    failed=1,
                    failed_matches=[],
                    season_name=season_name,
                    duration_seconds=0.0
                )
                pipeline_result['season_results'].append(failed_result)
        
        # Đánh giá kết quả tổng thể
        pipeline_result['success'] = (
            pipeline_result['successful_seasons'] == pipeline_result['total_seasons'] and
            pipeline_result['total_seasons'] > 0
        )
        
        return pipeline_result

    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
        raise
    except Exception as e:
        logger.critical("A critical unhandled error occurred during pipeline orchestration.", exc_info=True)
        return pipeline_result
    finally:
        pipeline_result['duration_seconds'] = (datetime.now() - start_time).total_seconds()
        if orchestrator:
            orchestrator.close()
        cleanup_resources()

def main() -> int:
    """Entry point chính của ứng dụng: Phân tích tham số, thiết lập và chạy pipeline."""
    # Đăng ký xử lý tín hiệu thoát an toàn
    signal.signal(signal.SIGINT, handle_graceful_shutdown)
    signal.signal(signal.SIGTERM, handle_graceful_shutdown)

    # Phân tích tham số dòng lệnh
    parser = argparse.ArgumentParser(
        description="SofaScore Data ETL Pipeline for Premier League.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--seasons', nargs='+', metavar='SEASON_NAME',
        help='Specific seasons to process (e.g., "2022/23" "2021/22").\nIf not provided, processes all target seasons from config.'
    )
    parser.add_argument(
        '--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default=None, help='Override the logging level from the environment.'
    )
    args = parser.parse_args()

    # Bước 1: THIẾT LẬP LOGGING - phải là bước đầu tiên
    setup_logging(log_level=args.log_level)

    try:
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("SofaScore ETL Pipeline Started")
        logger.info("=" * 60)
        
        pipeline_result = run_pipeline(specific_season_names=args.seasons)
        
        total_duration = datetime.now() - start_time
        logger.info("=" * 60)
        
        if pipeline_result['success']:
            logger.info("✓ PIPELINE COMPLETED SUCCESSFULLY in %.2f seconds.", total_duration.total_seconds())
            logger.info("Summary: %d/%d seasons processed, %d/%d matches loaded successfully.", 
                    pipeline_result['successful_seasons'], pipeline_result['total_seasons'],
                    pipeline_result['successful_matches'], pipeline_result['total_matches'])
            return 0  # Mã thoát 0 = THÀNH CÔNG
        else:
            logger.error("✗ PIPELINE COMPLETED WITH ERRORS in %.2f seconds.", total_duration.total_seconds())
            logger.error("Summary: %d/%d seasons processed, %d/%d matches loaded successfully.", 
                        pipeline_result['successful_seasons'], pipeline_result['total_seasons'],
                        pipeline_result['successful_matches'], pipeline_result['total_matches'])
            return 1  # Mã thoát 1 = THẤT BẠI
    
    except KeyboardInterrupt:
        logger.warning("\nPipeline interrupted by user. Final cleanup initiated.")
        return 130 # Mã thoát chuẩn cho Ctrl+C
    except Exception as e:
        logger.critical("A fatal unhandled error occurred in __main__: %s", e, exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = main()
    logger.info("Pipeline exiting with code %d.", exit_code)
    sys.exit(exit_code)