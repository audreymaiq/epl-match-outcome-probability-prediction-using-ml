# run_pipeline.py

import logging
import argparse
import time
from typing import List, Optional, Tuple, Dict, Any

from pybreaker import CircuitBreaker

# BƯỚC 1: KHỞI TẠO CÁC THÀNH PHẦN CƠ BẢN (QUAN TRỌNG NHẤT)
# Tuân thủ nghiêm ngặt thứ tự để giải quyết các vấn đề kiến trúc đã phân tích.
# 1.1: Tải biến môi trường từ file .env trước tiên.
from config.env_loader import load_environment
load_environment()

# 1.2: Sau khi có biến môi trường, thiết lập hệ thống logging.
from utils.logging_config import setup_logging, teardown_logging
setup_logging()

# BƯỚC 2: IMPORT CÁC THÀNH PHẦN CÒN LẠI CỦA HỆ THỐNG
from config.settings import get_config
from utils.db_connector import DatabaseConnector
from elt_pipeline.extract.sofascore_extractor import SofaScoreExtractor, SofaScoreEndpoints
from elt_pipeline.transform.sofascore_transformer import SofaScoreTransformer
from elt_pipeline.load.sofascore_loader import SofaScoreLoader, LoaderError

# --- Cấu hình logging cho file này ---
logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    """
    Lớp điều phối chính, chịu trách nhiệm thực thi toàn bộ pipeline ETL.
    """

    def __init__(self):
        """Khởi tạo tất cả các thành phần cần thiết cho pipeline."""
        logger.info("Initializing Pipeline Orchestrator...")
        
        # Lấy cấu hình đã được tải và xác thực
        self.config = get_config()
        
        # Thiết lập Circuit Breaker dựa trên cấu hình
        self.breaker = self._setup_circuit_breaker()
        
        # Khởi tạo các thành phần E-T-L
        self.extractor = SofaScoreExtractor(self.config.sofascore, self.config.scraping)
        self.transformer = SofaScoreTransformer(api_type='sofascore')
        # Lưu ý: Loader sẽ được khởi tạo sau, bên trong một DB session.
        
        logger.info("Orchestrator initialized successfully.")

    def _setup_circuit_breaker(self) -> CircuitBreaker:
        """Cấu hình và trả về một instance của CircuitBreaker."""
        fail_max = self.config.sofascore.circuit_breaker_threshold
        reset_timeout = self.config.sofascore.circuit_breaker_timeout
        logger.info(f"Setting up Circuit Breaker: fail_max={fail_max}, reset_timeout={reset_timeout}s")
        return CircuitBreaker(fail_max=fail_max, reset_timeout=reset_timeout)

    def run(self, specific_seasons: Optional[List[str]] = None):
        """
        Thực thi pipeline cho các mùa giải được chỉ định hoặc tất cả các mùa giải mục tiêu.
        
        Args:
            specific_seasons: Danh sách các mùa giải để chạy (ví dụ: ['2022/23', '2023/24']).
                              Nếu None, sẽ chạy tất cả các mùa giải từ config.
        """
        start_time = time.monotonic()
        logger.info("ETL Pipeline started.")
        
        # Lấy danh sách các mùa giải mục tiêu từ config
        target_seasons = self.config.get_target_seasons_with_ids()
        
        # Lọc các mùa giải nếu người dùng chỉ định
        seasons_to_process = self._filter_seasons(target_seasons, specific_seasons)
        
        if not seasons_to_process:
            logger.warning("No seasons to process after filtering. Exiting.")
            return

        total_processed_matches = 0
        total_success_loads = 0
        total_failed_loads = 0

        # Vòng lặp chính: xử lý từng mùa giải
        for year, season_name, season_id in seasons_to_process:
            try:
                logger.info(f"--- Processing season: {season_name} (ID: {season_id}) ---")
                
                # BƯỚC 3.1: EXTRACT
                raw_matches = self._extract_season_data(season_name, season_id)
                
                if not raw_matches:
                    logger.warning(f"No match data extracted for season {season_name}. Skipping to next season.")
                    continue
                
                # BƯỚC 3.2: TRANSFORM & LOAD
                # Giai đoạn này được gói gọn để xử lý transaction DB
                load_results = self._transform_and_load(raw_matches)
                
                # Cập nhật thống kê tổng
                total_processed_matches += load_results.get("total", 0)
                total_success_loads += load_results.get("success", 0)
                total_failed_loads += load_results.get("failed", 0)

            except Exception as e:
                logger.critical(
                    f"A critical unhandled error occurred while processing season {season_name}. "
                    f"Moving to the next season. Error: {e}",
                    exc_info=True
                )

        # BƯỚC 4: BÁO CÁO TỔNG KẾT
        end_time = time.monotonic()
        duration = end_time - start_time
        logger.info("=" * 50)
        logger.info("ETL Pipeline Finished - Overall Summary")
        logger.info(f"Total seasons processed: {len(seasons_to_process)}")
        logger.info(f"Total matches transformed: {total_processed_matches}")
        logger.info(f"Successfully loaded matches: {total_success_loads}")
        logger.info(f"Failed to load matches: {total_failed_loads}")
        logger.info(f"Total execution time: {duration:.2f} seconds")
        logger.info("=" * 50)

    def _filter_seasons(
        self,
        all_seasons: List[Tuple[int, str, int]],
        specific_seasons: Optional[List[str]]
    ) -> List[Tuple[int, str, int]]:
        """Lọc danh sách các mùa giải dựa trên input của người dùng."""
        if not specific_seasons:
            logger.info(f"Processing all {len(all_seasons)} target seasons from config.")
            return all_seasons
        
        specific_set = set(specific_seasons)
        filtered = [s for s in all_seasons if s[1] in specific_set]
        logger.info(f"Processing {len(filtered)}/{len(all_seasons)} seasons specified by user: {specific_seasons}")
        return filtered

    def _extract_season_data(self, season_name: str, season_id: int) -> List[Dict[str, Any]]:
        """
        Thực thi giai đoạn Extract cho một mùa giải cụ thể.
        """
        logger.info(f"Extracting match list for season {season_name}...")
        try:
            # Lấy danh sách tất cả các trận đấu trong mùa giải
            # Sử dụng fetch_paginated_events vì nó là alias của fetch_paginated_data với response_field="events"
            raw_matches = self.extractor.fetch_paginated_events(
                endpoint=SofaScoreEndpoints.SEASON_MATCHES_LAST,
                breaker=self.breaker,
                tournament_id=self.config.sofascore.premier_league_id,
                season_id=season_id
            )
            logger.info(f"Extracted {len(raw_matches)} raw match entries for season {season_name}.")
            return raw_matches
        except Exception as e:
            logger.error(f"Failed to extract data for season {season_name}: {e}", exc_info=True)
            return []

    def _transform_and_load(self, raw_matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Thực thi giai đoạn Transform và Load cho một loạt dữ liệu thô.
        Quản lý transaction của DB ở đây.
        """
        # BƯỚC 3.2.1: TRANSFORM
        logger.info(f"Transforming {len(raw_matches)} raw matches...")
        parsed_matches = []
        for raw_match in raw_matches:
            # Trong tương lai, có thể lấy thêm events/lineups ở đây và truyền vào transformer
            # Ví dụ: raw_events = self.extractor.fetch_incidents(raw_match['id'])
            transformed = self.transformer.transform_match_and_events(raw_match, raw_events=None)
            if transformed:
                parsed_matches.append(transformed)
        
        logger.info(f"Successfully transformed {len(parsed_matches)} matches.")
        if not parsed_matches:
            return {"total": 0, "success": 0, "failed": 0, "failed_ids": []}

        # BƯỚC 3.2.2: LOAD
        # Sử dụng `session_scope` để đảm bảo transaction được quản lý đúng cách
        logger.info(f"Loading {len(parsed_matches)} transformed matches into the database...")
        try:
            with DatabaseConnector.session_scope() as session:
                # Khởi tạo Loader với session (Dependency Injection)
                loader = SofaScoreLoader(session)
                
                # Thực hiện load hàng loạt
                results = loader.bulk_load_matches(parsed_matches)
                
                logger.info("Load process for batch completed.", extra={"results": results})
                return results
        except (LoaderError, Exception) as e:
            logger.error(f"Database loading failed at the session level: {e}", exc_info=True)
            return {"total": len(parsed_matches), "success": 0, "failed": len(parsed_matches), "failed_ids": [m.external_id for m in parsed_matches]}

    def close(self):
        """Dọn dẹp tài nguyên khi pipeline kết thúc."""
        logger.info("Closing orchestrator resources...")
        self.extractor.close()
        logger.info("Orchestrator closed.")


def main():
    """Hàm chính để chạy pipeline từ dòng lệnh."""
    parser = argparse.ArgumentParser(description="Run the Premier League ETL pipeline.")
    parser.add_argument(
        "--seasons",
        nargs='+',
        help="Specify one or more seasons to process (e.g., '2022/23' '2023/24'). "
             "If not provided, all target seasons from config will be processed."
    )
    args = parser.parse_args()

    orchestrator = None
    try:
        # Kiểm tra kết nối DB trước khi bắt đầu công việc nặng
        if not DatabaseConnector.check_connection():
            logger.critical("Database connection check failed. Aborting pipeline.")
            return

        orchestrator = PipelineOrchestrator()
        orchestrator.run(specific_seasons=args.seasons)

    except Exception as e:
        logger.critical(f"An unrecoverable error occurred in the pipeline: {e}", exc_info=True)
    finally:
        if orchestrator:
            orchestrator.close()
        # Dọn dẹp tài nguyên logging (flush buffer, etc.)
        teardown_logging()

if __name__ == "__main__":
    main()