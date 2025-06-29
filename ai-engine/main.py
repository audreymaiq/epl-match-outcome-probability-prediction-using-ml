# main_correct.py

import sys
import signal
import logging
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
import argparse

from utils.logging_config import setup_logging
# Bây giờ mới thiết lập logging, có thể truyền tham số từ command line
# setup_logging() # Sẽ được gọi trong main() để nhận log_level

# --- Bước 2: Import các thành phần của hệ thống ---
from config.settings import get_config
from elt_pipeline.extract.sofascore_extractor import SofascoreClient, ClientError
# Giả sử bạn có các module này để thực hiện Transform và Load
# from elt_pipeline.transform.sofascore_parser import SofascoreDataParser 
# from elt_pipeline.load.database_loader import DatabaseLoader

logger = logging.getLogger(__name__)


# --- Các Lớp/Hàm Giả Lập cho Transform và Load ---
# Trong thực tế, bạn sẽ tạo các file riêng cho chúng
class SofascoreDataParser:
    """Chịu trách nhiệm Transform: phân tích và chuẩn hóa dữ liệu thô."""
    def __init__(self):
        # Có thể import các mappers từ field_mappings ở đây
        logger.info("Data parser initialized.")

    def parse_events_data(self, raw_events_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Đây là nơi bạn dùng field_mappings.py
        # Logic biến đổi JSON thô thành danh sách các trận đấu đã được làm sạch
        logger.info(f"Parsing raw events data...")
        # ... logic biến đổi ở đây ...
        # Ví dụ:
        parsed_matches = []
        raw_events = raw_events_data.get("events", [])
        for event in raw_events:
            parsed_matches.append({
                "match_id": event.get("id"),
                "status": event.get("status", {}).get("description"),
                "home_team": event.get("homeTeam", {}).get("name"),
                "away_team": event.get("awayTeam", {}).get("name"),
                "start_timestamp": event.get("startTimestamp"),
            })
        logger.info(f"Parsed {len(parsed_matches)} matches.")
        return parsed_matches

class DatabaseLoader:
    """Chịu trách nhiệm Load: lưu dữ liệu vào DB."""
    def __init__(self):
        # Sử dụng db_connector
        from utils.db_connector import DatabaseConnector
        self.db_connector = DatabaseConnector
        logger.info("Database loader initialized.")

    def save_matches(self, matches: List[Dict[str, Any]], season_name: str):
        # Đây là nơi bạn dùng db_connector.py
        logger.info(f"Saving {len(matches)} matches for season {season_name} to database...")
        # with self.db_connector.session_scope() as session:
            # ... logic thêm vào DB ở đây ...
        logger.info("Matches saved successfully.")


# --- Các Hàm Điều Phối (Orchestration Functions) ---
def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}. Shutting down gracefully...")
    sys.exit(0)

def process_season(client: SofascoreClient, parser: SofascoreDataParser, loader: DatabaseLoader, season_id: int, season_name: str, tournament_id: int) -> bool:
    """
    Điều phối quy trình E-T-L cho một mùa giải.
    """
    try:
        logger.info(f"--- Processing season: {season_name} (ID: {season_id}) ---")
        start_time = datetime.now()

        # E - Extract: Client chỉ lấy dữ liệu thô
        logger.info(f"Extracting raw events data...")
        # Giả sử client có phương thức này (bạn cần định nghĩa nó)
        # Nó sẽ lặp qua các trang và trả về toàn bộ JSON
        raw_data = client.get_all_events_for_season(
            tournament_id=tournament_id,
            season_id=season_id
        )

        if not raw_data or not raw_data.get("events"):
            logger.warning(f"No matches found for season {season_name}")
            return True

        # T - Transform: Parser phân tích dữ liệu thô
        matches_to_load = parser.parse_events_data(raw_data)

        # L - Load: Loader lưu dữ liệu đã chuẩn hóa
        loader.save_matches(matches_to_load, season_name)

        duration = datetime.now() - start_time
        logger.info(f"✓ Season {season_name} completed in {duration.total_seconds():.2f} seconds")
        return True

    except ClientError as e:
        logger.error(f"✗ Client error processing season {season_name}: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error processing season {season_name}: {e}", exc_info=True)
        return False

def run_extraction(specific_seasons: Optional[List[str]] = None):
    """Hàm điều phối chính."""
    config = get_config()

    # Khởi tạo các thành phần theo đúng kiến trúc
    client = SofascoreClient(
        settings=config.sofascore,
        scraping_settings=config.scraping
    )
    parser = SofascoreDataParser()
    loader = DatabaseLoader()

    # Lấy danh sách mùa giải từ cấu hình
    # Giả định get_target_seasons_with_ids đã có trong SofascoreSettings
    all_seasons = config.get_target_seasons_with_ids()
    tournament_id = config.sofascore.premier_league_id

    # ... (giữ nguyên logic filter seasons của bạn) ...
    seasons_to_process = all_seasons # Giả định xử lý tất cả

    success_count = 0
    error_count = 0

    for year, season_name, sofascore_id in seasons_to_process:
        if process_season(client, parser, loader, sofascore_id, season_name, tournament_id):
            success_count += 1
        else:
            error_count += 1

    # ... (giữ nguyên logic summary của bạn) ...
    return error_count == 0

def main():
    """Entry point chính của chương trình."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parser = argparse.ArgumentParser(description='SofaScore Data Extraction')
    parser.add_argument('--seasons', nargs='+', help='Specific seasons to process', default=None)
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default=None, help='Override logging level from .env')
    args = parser.parse_args()

    # Sửa lại cách thiết lập logging
    setup_logging(log_level=args.log_level) 
    
    try:
        logger.info("=" * 60)
        logger.info("SofaScore Data Extraction Started")
        logger.info("=" * 60)
        
        start_time = datetime.now()
        success = run_extraction(args.seasons)
        total_duration = datetime.now() - start_time

        logger.info("=" * 60)
        if success:
            logger.info(f"✓ Extraction completed successfully in {total_duration.total_seconds():.2f} seconds")
            sys.exit(0)
        else:
            logger.error(f"✗ Extraction completed with errors in {total_duration.total_seconds():.2f} seconds")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nProcess interrupted by user.")
        sys.exit(130)
    except Exception as e:
        logger.critical(f"A fatal unhandled error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()