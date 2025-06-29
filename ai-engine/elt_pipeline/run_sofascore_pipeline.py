# elt_pipeline\run_sofascore_pipeline.py

import sys
import signal
import logging
import argparse
from datetime import datetime
from typing import List, Optional

# --- Thiết lập logging và các import cơ bản ---
from utils.logging_config import setup_logging

# --- Import các thành phần của hệ thống ---
try:
    from config.settings import get_config
    from utils.db_connector import DatabaseConnector
    from elt_pipeline.extract.sofascore_extractor import SofaScoreExtractor
    from elt_pipeline.extract.sofascore_endpoints import SofaScoreEndpoints
    from elt_pipeline.transform.sofascore_transformer import SofaScoreTransformer
    from elt_pipeline.load.sofascore_loader import SofaScoreLoader
except ImportError as e:
    print(f"Critical Import Error: {e}. Please ensure your PYTHONPATH is set correctly.")
    sys.exit(1)

# --- Khởi tạo logger sau khi cấu hình ---
logger = logging.getLogger(__name__)

# --- Lớp Điều phối (Orchestrator) ---
class SofaScoreETLOrchestrator:
    """Điều phối toàn bộ quy trình: Extract -> Transform -> Load."""

    def __init__(self, extractor: SofaScoreExtractor, transformer: SofaScoreTransformer):
        self.extractor = extractor
        self.transformer = transformer

    def process_season(self, season_id: int, season_name: str, tournament_id: int) -> bool:
        """
        Xử lý toàn bộ một mùa giải và trả về True nếu thành công, False nếu có lỗi.
        """
        logger.info(f"--- Starting ETL process for season: {season_name} (ID: {season_id}) ---")
        season_success = True
        
        # --- EXTRACT (Summaries) ---
        raw_summaries = self.extractor.fetch_paginated_data(
            SofaScoreEndpoints.SEASON_MATCHES,
            tournament_id=tournament_id,
            season_id=season_id
        )

        total_matches = len(raw_summaries)
        if total_matches == 0:
            logger.warning(f"No match summaries found for season {season_name}. Skipping.")
            return True # Coi như thành công vì không có gì để xử lý
            
        logger.info(f"Extracted {total_matches} match summaries for season {season_name}.")

        for i, raw_summary in enumerate(raw_summaries):
            ext_match_id = raw_summary.get("id")
            if not ext_match_id:
                logger.warning("Found a match summary without an ID. Skipping.", extra={"summary": raw_summary})
                continue

            log_extra = {"ext_id": ext_match_id, "progress": f"{i+1}/{total_matches}"}
            logger.info("Processing match", extra=log_extra)

            try:
                # --- EXTRACT (Details) ---
                raw_detail = self.extractor.fetch_match_detail(ext_match_id)
                if not raw_detail:
                    logger.error("Failed to extract match detail. Skipping match.", extra=log_extra)
                    season_success = False
                    continue
                
                # --- TRANSFORM ---
                parsed_match = self.transformer.transform_match_data(raw_summary, raw_detail)
                if not parsed_match:
                    logger.error("Failed to transform match data. Skipping match.", extra=log_extra)
                    season_success = False
                    continue

                # --- LOAD ---
                with DatabaseConnector.session_scope() as session:
                    loader = SofaScoreLoader(session)
                    loader.load_full_match_data(parsed_match)
                
                logger.debug("Successfully loaded match data.", extra={"ext_id": ext_match_id, "int_id": parsed_match.internal_id})

            except Exception as e:
                logger.error("An unexpected error occurred while processing a match.",
                            extra=log_extra, exc_info=True)
                season_success = False
        
        logger.info(f"--- Finished ETL process for season: {season_name} ---")
        return season_success

# --- Các hàm hỗ trợ cho main() ---
def handle_graceful_shutdown(signum, frame):
    """Xử lý tín hiệu Ctrl+C để tắt chương trình một cách an toàn."""
    logger.warning(f"Received signal {signum}. Shutting down gracefully...")
    # Có thể thêm logic dọn dẹp tại đây nếu cần
    sys.exit(130) # Mã thoát chuẩn cho việc bị ngắt bởi người dùng

def run_pipeline(specific_season_names: Optional[List[str]] = None):
    """
    Hàm logic chính, điều phối toàn bộ pipeline.
    Trả về True nếu tất cả các mùa giải đều thành công, ngược lại False.
    """
    try:
        config = get_config()
    except Exception as e:
        logger.critical("Failed to load configuration. Aborting.", exc_info=True)
        return False

    extractor = SofaScoreExtractor(config.sofascore, config.scraping)
    transformer = SofaScoreTransformer()
    orchestrator = SofaScoreETLOrchestrator(extractor, transformer)
    
    overall_success = True
    
    try:
        # Lấy danh sách mùa giải từ config
        all_seasons_with_ids = config.get_target_seasons_with_ids()
        
        # Lọc danh sách nếu người dùng chỉ định
        seasons_to_process = []
        if specific_season_names:
            specific_set = set(specific_season_names)
            seasons_to_process = [
                (year, name, sid) for year, name, sid in all_seasons_with_ids if name in specific_set
            ]
            if not seasons_to_process:
                logger.error(f"None of the specified seasons {specific_season_names} are configured to be fetched.")
                return False
        else:
            seasons_to_process = all_seasons_with_ids

        logger.info(f"Pipeline will process {len(seasons_to_process)} season(s): {[s[1] for s in seasons_to_process]}")
        
        # Xử lý từng mùa giải
        for _, season_name, season_id in seasons_to_process:
            if not orchestrator.process_season(
                season_id=season_id,
                season_name=season_name,
                tournament_id=config.sofascore.premier_league_id
            ):
                overall_success = False # Nếu một mùa thất bại, toàn bộ pipeline thất bại
                
    except Exception as e:
        logger.critical("A critical error occurred during pipeline orchestration.", exc_info=True)
        overall_success = False
    finally:
        extractor.close()
        
    return overall_success

# --- Entry Point Chính ---
def main():
    """Entry point của ứng dụng: phân tích tham số, thiết lập và chạy pipeline."""
    
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
        help='Specific seasons to process (e.g., "2022/23" "2021/22").\nIf not provided, processes all target seasons from config.',
        default=None
    )
    parser.add_argument(
        '--log-level', 
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], 
        default=None, 
        help='Override the logging level defined in the environment.'
    )
    args = parser.parse_args()

    # 3. Thiết lập logging với tùy chọn từ dòng lệnh
    setup_logging(log_level=args.log_level)

    # 4. Chạy pipeline và xử lý kết quả
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("SofaScore ETL Pipeline Started")
    logger.info("=" * 60)
    
    success = run_pipeline(specific_season_names=args.seasons)
    
    total_duration = datetime.now() - start_time
    logger.info("=" * 60)
    
    if success:
        logger.info(f"✓ Pipeline completed successfully in {total_duration.total_seconds():.2f} seconds.")
        sys.exit(0) # Mã thoát 0 = THÀNH CÔNG
    else:
        logger.error(f"✗ Pipeline completed with errors in {total_duration.total_seconds():.2f} seconds.")
        sys.exit(1) # Mã thoát 1 = THẤT BẠI

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Bắt các lỗi nghiêm trọng không lường trước được ở tầng cao nhất
        logging.getLogger(__name__).critical(f"A fatal unhandled error occurred in __main__: {e}", exc_info=True)
        sys.exit(1)