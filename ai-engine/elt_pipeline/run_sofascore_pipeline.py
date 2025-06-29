# elt_pipeline/run_sofascore_pipeline.py

import sys
import signal
import logging
import argparse
from datetime import datetime
from typing import List, Optional

# --- Thiết lập import và xử lý lỗi import sớm ---
try:
    # 1. Import các thành phần nền tảng
    from utils.logging_config import setup_logging
    from config.settings import get_config
    from utils.db_connector import DatabaseConnector

    # 2. Import các thành phần của pipeline
    from elt_pipeline.extract.sofascore_extractor import SofaScoreExtractor
    from elt_pipeline.extract.sofascore_endpoints import SofaScoreEndpoints
    # Giả định bạn đã tạo file data_structures.py và sử dụng Transformer mới
    from elt_pipeline.transform.data_structures import ParsedMatch
    from elt_pipeline.transform.sofascore_transformer import SofaScoreTransformer
    from elt_pipeline.load.sofascore_loader import SofaScoreLoader
except ImportError as e:
    # Lỗi này xảy ra trước khi logging được thiết lập, nên dùng print
    print(f"CRITICAL IMPORT ERROR: {e}\n"
        f"Please ensure your project structure is correct and PYTHONPATH is set.\n"
        f"Run 'pip install -e .' from the project root if you haven't already.", file=sys.stderr)
    sys.exit(1)

# Khởi tạo logger sau khi đã import thành công logging_config
logger = logging.getLogger(__name__)

# --- Lớp Điều phối (Orchestrator) ---
class SofaScoreETLOrchestrator:
    """
    Điều phối toàn bộ quy trình ETL cho từng trận đấu.
    Quản lý luồng dữ liệu: Extract -> Transform -> Load.
    """

    def __init__(self, extractor: SofaScoreExtractor, transformer: SofaScoreTransformer):
        self.extractor = extractor
        self.transformer = transformer

    def process_season(self, season_id: int, season_name: str, tournament_id: int) -> dict:
        """
        Xử lý toàn bộ một mùa giải, trả về kết quả chi tiết.
        """
        logger.info(f"--- Starting ETL for season: {season_name} (ID: {season_id}) ---")
        
        # --- EXTRACT (Summaries) ---
        raw_summaries = self.extractor.fetch_paginated_data(
            SofaScoreEndpoints.SEASON_MATCHES,
            tournament_id=tournament_id,
            season_id=season_id
        )

        total_matches = len(raw_summaries)
        if not total_matches:
            logger.warning(f"No match summaries found for season {season_name}. Skipping.")
            return {"total": 0, "success": 0, "failed": 0}
            
        logger.info(f"Extracted {total_matches} match summaries for season {season_name}.")

        results = {"total": total_matches, "success": 0, "failed": 0, "failed_ids": []}

        for i, raw_summary in enumerate(raw_summaries):
            ext_match_id = raw_summary.get("id")
            if not ext_match_id:
                logger.warning("Skipping match summary without an ID.", extra={"summary": raw_summary})
                results["failed"] += 1
                continue

            log_extra = {"ext_id": ext_match_id, "progress": f"{i+1}/{total_matches}", "season": season_name}
            logger.info("Processing match...", extra=log_extra)

            try:
                # --- EXTRACT (Details) ---
                raw_detail = self.extractor.fetch_match_detail(int(ext_match_id))
                
                # --- TRANSFORM ---
                parsed_match = self.transformer.transform_match(raw_summary, raw_detail)
                if not parsed_match:
                    logger.error("Failed to transform match data.", extra=log_extra)
                    results["failed"] += 1
                    results["failed_ids"].append(ext_match_id)
                    continue

                # --- LOAD ---
                # Mỗi trận đấu được xử lý trong một transaction riêng để đảm bảo tính toàn vẹn
                with DatabaseConnector.session_scope() as session:
                    loader = SofaScoreLoader(session)
                    match_id = loader.load_full_match_data(parsed_match)
                    
                    if not match_id:
                        logger.error("Failed to load match data into database.", extra=log_extra)
                        # session_scope sẽ tự động rollback
                        raise RuntimeError("Loader returned None, triggering transaction rollback.")
                        
                logger.debug(f"Successfully loaded match.", extra={"ext_id": ext_match_id, "int_id": match_id})
                results["success"] += 1
                        
            except Exception as e:
                # Bất kỳ lỗi nào trong khối try (Extract Detail, Transform, Load) sẽ được bắt ở đây
                logger.error(f"Failed to process match. Error: {e}", extra=log_extra, exc_info=True)
                results["failed"] += 1
                results["failed_ids"].append(ext_match_id)
        
        logger.info(f"--- Finished ETL for season: {season_name}. "
                    f"Success: {results['success']}, Failed: {results['failed']} ---")
        return results

# --- Các hàm hỗ trợ ---
def handle_graceful_shutdown(signum, frame):
    """Xử lý tín hiệu Ctrl+C để tắt chương trình một cách an toàn."""
    logger.warning(f"Received signal {signum}. Shutting down gracefully...")
    sys.exit(130)  # Mã thoát chuẩn cho việc bị ngắt bởi người dùng

def run_pipeline(specific_season_names: Optional[List[str]] = None) -> bool:
    """
    Hàm logic chính: Khởi tạo các thành phần và điều phối pipeline qua các mùa giải.
    Trả về True nếu tất cả các mùa giải không có lỗi, ngược lại False.
    """
    extractor = None  # Khai báo để có thể truy cập trong khối finally
    try:
        # --- KHỞI TẠO ---
        # Khởi tạo các thành phần cốt lõi một lần duy nhất
        config = get_config()
        extractor = SofaScoreExtractor(config.sofascore, config.scraping)
        transformer = SofaScoreTransformer(api_type='sofascore')
        orchestrator = SofaScoreETLOrchestrator(extractor, transformer)
        
        # Kiểm tra kết nối DB trước khi bắt đầu
        if not DatabaseConnector.check_connection():
            logger.critical("Database connection failed. Aborting pipeline.")
            return False

        # --- LẤY DANH SÁCH MÙA GIẢI CẦN XỬ LÝ ---
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
        # Đảm bảo session của extractor luôn được đóng, dù thành công hay thất bại
        if extractor:
            extractor.close()

# --- Entry Point Chính ---
def main():
    """Entry point của ứng dụng: Phân tích tham số, thiết lập và chạy pipeline."""
    
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
        sys.exit(0)  # Mã thoát 0 = THÀNH CÔNG
    else:
        logger.error(f"✗ PIPELINE COMPLETED WITH ERRORS in {total_duration.total_seconds():.2f} seconds.")
        sys.exit(1)  # Mã thoát 1 = THẤT BẠI

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Bắt các lỗi nghiêm trọng không lường trước được ở tầng cao nhất
        # (ví dụ lỗi trong argparse, signal...)
        logger.critical(f"A fatal unhandled error occurred in __main__: {e}", exc_info=True)
        sys.exit(1)