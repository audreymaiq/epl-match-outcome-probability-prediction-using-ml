# elt_pipeline/run_sofascore_pipeline.py

import sys
import signal
import logging
import argparse
from datetime import datetime
from typing import List, Optional, Dict, Any
import pybreaker
import requests_cache

# --- Thiết lập import và xử lý lỗi import sớm ---
try:
    # 1. Import các thành phần nền tảng
    from utils.logging_config import setup_logging
    from config.settings import get_config, ConfigManager
    from utils.db_connector import DatabaseConnector

    # 2. Import các thành phần của pipeline
    from elt_pipeline.extract.sofascore_extractor import SofaScoreExtractor
    from elt_pipeline.extract.sofascore_endpoints import SofaScoreEndpoints
    from elt_pipeline.transform.sofascore_transformer import SofaScoreTransformer
    from elt_pipeline.load.sofascore_loader import SofaScoreLoader
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}\n"
        f"Please ensure your project structure is correct and PYTHONPATH is set.\n"
        f"Run 'pip install -e .' from the project root if you haven't already.", file=sys.stderr)
    sys.exit(1)

# Khởi tạo logger sau khi đã import thành công logging_config
logger = logging.getLogger(__name__)

# --- Lớp Điều phối (Orchestrator) ---
class SofaScoreETLOrchestrator:
    """
    Điều phối toàn bộ quy trình ETL.
    Quản lý Session Rotation và Circuit Breaker.
    """

    def __init__(self, config: ConfigManager, transformer: SofaScoreTransformer):
        self.config = config
        self.transformer = transformer
        self.extractor: Optional[SofaScoreExtractor] = None
        self.requests_since_rotation = 0

        # Khởi tạo Circuit Breaker từ cấu hình
        self.breaker = pybreaker.CircuitBreaker(
            fail_max=self.config.sofascore.circuit_breaker_threshold,
            reset_timeout=self.config.sofascore.circuit_breaker_timeout,
        )
        logger.info(
            f"Circuit Breaker initialized: fail_max={self.breaker.fail_max}, "
            f"reset_timeout={self.breaker.reset_timeout}s"
        )

    def _get_extractor(self) -> SofaScoreExtractor:
        """
        Quản lý việc tạo và xoay vòng (rotate) Extractor/Session.
        Hàm này là cốt lõi của cơ chế Session Rotation.
        """
        rotation_interval = self.config.sofascore.session_rotation_interval
        
        # Tạo mới nếu chưa có, hoặc nếu đã đến lúc xoay vòng
        if self.extractor is None or self.requests_since_rotation >= rotation_interval:
            if self.extractor:
                logger.info(
                    f"Rotating session after {self.requests_since_rotation} requests "
                    f"(interval: {rotation_interval})."
                )
                self.extractor.close()

            self.extractor = SofaScoreExtractor(self.config.sofascore, self.config.scraping)
            self.requests_since_rotation = 0
        
        return self.extractor

    def _process_single_match(self, raw_summary: Dict[str, Any], season_name: str, total_matches: int, current_index: int):
        """Xử lý logic cho một trận đấu duy nhất."""
        ext_match_id = raw_summary.get("id")
        if not ext_match_id:
            logger.warning("Skipping match summary without an ID.", extra={"summary": raw_summary})
            return False

        log_extra = {"ext_id": ext_match_id, "progress": f"{current_index+1}/{total_matches}", "season": season_name}
        logger.info("Processing match...", extra=log_extra)
        
        try:
            extractor = self._get_extractor()
            
            # --- EXTRACT ---
            # Truyền circuit breaker vào hàm fetch
            raw_detail = extractor.fetch_match_detail(int(ext_match_id), breaker=self.breaker)
            self.requests_since_rotation += 1 # Đếm request
            if raw_detail is None:
                # Nếu trả về None, có thể do 404 hoặc circuit breaker đang mở
                # Lỗi đã được log trong extractor
                return False

            # --- TRANSFORM ---
            parsed_match = self.transformer.transform_match(raw_summary, raw_detail)
            if not parsed_match:
                logger.error("Failed to transform match data.", extra=log_extra)
                return False

            # --- LOAD ---
            with DatabaseConnector.session_scope() as session:
                loader = SofaScoreLoader(session)
                match_id = loader.load_full_match_data(parsed_match)
                if not match_id:
                    raise RuntimeError("Loader returned None, triggering transaction rollback.")
            
            logger.debug(f"Successfully loaded match.", extra={"ext_id": ext_match_id, "int_id": match_id})
            return True

        except pybreaker.CircuitBreakerError as e:
            logger.critical(f"Circuit Breaker is open. Stopping processing for this season. Error: {e}", extra=log_extra)
            raise  # Ném lại lỗi để dừng vòng lặp của mùa giải
        except Exception as e:
            logger.error(f"Failed to process match. Error: {e}", extra=log_extra, exc_info=True)
            return False

    def process_season(self, season_id: int, season_name: str, tournament_id: int) -> dict:
        """Xử lý toàn bộ một mùa giải, trả về kết quả chi tiết."""
        logger.info(f"--- Starting ETL for season: {season_name} (ID: {season_id}) ---")
        
        # Bọc fetch_paginated_data trong try-except
        try:
            extractor = self._get_extractor()
            # --- EXTRACT (Summaries) ---
            raw_summaries, requests_count = extractor.fetch_paginated_data(
                SofaScoreEndpoints.SEASON_MATCHES,
                breaker=self.breaker,
                tournament_id=tournament_id,
                season_id=season_id
            )
            self.requests_since_rotation += requests_count # Cập nhật số request đã thực hiện
        except pybreaker.CircuitBreakerError as e:
            logger.critical(f"Circuit Breaker is open when fetching season data. Skipping season {season_name}. Error: {e}")
            return {"total": 0, "success": 0, "failed": 0}
        except Exception as e:
            logger.error(f"Failed to fetch season data for {season_name}. Error: {e}", exc_info=True)
            return {"total": 0, "success": 0, "failed": 0}

        total_matches = len(raw_summaries)
        if not total_matches:
            logger.warning(f"No match summaries found for season {season_name}. Skipping.")
            return {"total": 0, "success": 0, "failed": 0}
            
        logger.info(f"Extracted {total_matches} match summaries for season {season_name}.")

        results = {"total": total_matches, "success": 0, "failed": 0, "failed_ids": []}

        for i, raw_summary in enumerate(raw_summaries):
            try:
                success = self._process_single_match(raw_summary, season_name, total_matches, i)
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    match_id = raw_summary.get("id")
                    if match_id:
                        results["failed_ids"].append(match_id)
            except pybreaker.CircuitBreakerError:
                # Nếu circuit breaker mở, dừng xử lý mùa giải này ngay lập tức
                remaining_matches = total_matches - (i + 1)
                results["failed"] += remaining_matches
                logger.error(f"Aborting season {season_name} due to open circuit breaker. {remaining_matches} matches skipped.")
                break # Thoát khỏi vòng lặp for

        logger.info(f"--- Finished ETL for season: {season_name}. "
                    f"Success: {results['success']}, Failed: {results['failed']} ---")
        return results

    def close(self):
        """Dọn dẹp tài nguyên."""
        if self.extractor:
            self.extractor.close()

# --- Các hàm hỗ trợ ---
def handle_graceful_shutdown(signum, frame):
    """Xử lý tín hiệu Ctrl+C để tắt chương trình một cách an toàn."""
    raise KeyboardInterrupt 

def setup_cache(config: ConfigManager):
    """Kích hoạt caching nếu được cấu hình."""
    if config.scraping.enable_cache:
        try:
            # Dùng install_cache để patch toàn cục.
            # Nó đủ thông minh để hoạt động với các thư viện tuân thủ API của requests.
            requests_cache.install_cache(
                'sofascore_cache',
                backend='sqlite',
                expire_after=config.scraping.cache_ttl,
                allowable_methods=['GET']
            )
            logger.info(f"HTTP Caching is ENABLED via global patch. TTL: {config.scraping.cache_ttl} seconds.")
        except Exception as e:
            logger.error(f"Failed to enable requests-cache: {e}")
    else:
        logger.info("HTTP Caching is DISABLED.")

def cleanup_cache():
    """Dọn dẹp cache nếu đang được sử dụng."""
    if requests_cache.is_installed():
        try:
            requests_cache.uninstall_cache()
            logger.info("HTTP Caching uninstalled.")
        except Exception as e:
            logger.warning(f"Failed to uninstall cache: {e}")

def run_pipeline(specific_season_names: Optional[List[str]] = None) -> bool:
    orchestrator = None
    try:
        config = get_config()
        
        # --- Thiết lập cache trước khi làm bất cứ điều gì ---
        setup_cache(config)
        
        transformer = SofaScoreTransformer(api_type='sofascore')
        orchestrator = SofaScoreETLOrchestrator(config, transformer)
        
        if not DatabaseConnector.check_connection():
            logger.critical("Database connection failed. Aborting pipeline.")
            return False

        all_seasons_from_config = config.get_target_seasons_with_ids()
        
        # Lọc danh sách nếu người dùng chỉ định
        if specific_season_names:
            specific_set = set(specific_season_names)
            seasons_to_process = [s for s in all_seasons_from_config if s[1] in specific_set]
            if not seasons_to_process:
                logger.error(f"None of the specified seasons {specific_season_names} are configured to be fetched.")
                return False
        else:
            seasons_to_process = all_seasons_from_config

        logger.info(f"Pipeline will process {len(seasons_to_process)} season(s): "
                    f"{[s[1] for s in seasons_to_process]}")
        
        # --- CHẠY PIPELINE CHO TỪNG MÙA GIẢI ---
        total_failed_matches = 0
        for _, season_name, season_id in seasons_to_process:
            season_results = orchestrator.process_season(
                season_id=season_id,
                season_name=season_name,
                tournament_id=config.sofascore.premier_league_id
            )
            total_failed_matches += season_results.get("failed", 0)
        
        return total_failed_matches == 0 # Trả về True nếu không có trận nào thất bại

    except Exception as e:
        logger.critical("A critical error occurred during pipeline orchestration.", exc_info=True)
        return False
    finally:
        if orchestrator:
            orchestrator.close()
        cleanup_cache()

# --- Entry Point Chính ---
def main():
    """Entry point của ứng dụng: Phân tích tham số, thiết lập và chạy pipeline."""
    
    # Sử dụng cấu trúc try...except...finally và trả về exit_code
    exit_code = 1
    try:
        # 1. Bắt các tín hiệu để tắt an toàn
        signal.signal(signal.SIGINT, handle_graceful_shutdown)
        signal.signal(signal.SIGTERM, handle_graceful_shutdown)

        # 2. Phân tích tham số dòng lệnh
        parser = argparse.ArgumentParser(
            description="SofaScore Data ETL Pipeline for Premier League.",
            formatter_class=argparse.RawTextHelpFormatter
        )
        parser.add_argument(
            '--seasons', 
            nargs='+', 
            metavar='SEASON_NAME',
            help='Specific seasons to process (e.g., "2022/23" "2021/22").\n'
                'If not provided, processes all target seasons from config.',
            default=None
        )
        parser.add_argument(
            '--log-level', 
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], 
            default=None, 
            help='Override the logging level defined in the environment.'
        )
        args = parser.parse_args()

        # 3. THIẾT LẬP LOGGING (bước đầu tiên và quan trọng nhất)
        # env_loader sẽ được gọi ngầm trong get_config() sau, nhưng logging vẫn
        # có thể được override bởi tham số dòng lệnh.
        setup_logging(log_level=args.log_level)

        # 4. Chạy pipeline và xử lý kết quả
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("SofaScore ETL Pipeline Started")
        logger.info("=" * 60)
        
        pipeline_succeeded = run_pipeline(specific_season_names=args.seasons)
        
        total_duration = datetime.now() - start_time
        logger.info("=" * 60)
        
        if pipeline_succeeded:
            logger.info(f"✓ PIPELINE COMPLETED SUCCESSFULLY in {total_duration.total_seconds():.2f} seconds.")
            return 0  # Mã thoát 0 = THÀNH CÔNG
        else:
            logger.error(f"✗ PIPELINE COMPLETED WITH ERRORS in {total_duration.total_seconds():.2f} seconds.")
            return 1  # Mã thoát 1 = THẤT BẠI
        exit_code = 0 if pipeline_succeeded else 1
    
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Pipeline interrupted by user.", file=sys.stderr)
        exit_code = 130
    except Exception as e:
        # Bắt các lỗi nghiêm trọng khác
        if 'logger' in globals() and logger.handlers:
            logger.critical(f"A fatal unhandled error occurred in __main__: {e}", exc_info=True)
        else:
            print(f"CRITICAL ERROR (logger not available): {e}", file=sys.stderr)
        exit_code = 1
    finally:
        # atexit sẽ tự động gọi teardown_logging.
        cleanup_cache() 
        print("[SHUTDOWN] Cleanup complete. Exiting.", file=sys.stderr)
        return exit_code

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)