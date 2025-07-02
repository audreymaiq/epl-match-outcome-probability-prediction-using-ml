# scripts/run_integration_test.py

import logging
import json
import os
import random
import time
from datetime import date, datetime
from enum import Enum
from pathlib import Path

# --- Thiết lập môi trường và import ---
# Đảm bảo các import này hoạt động từ vị trí bạn chạy script.
# Cách tốt nhất là chạy script từ thư mục gốc của dự án.
try:
    from config.settings import get_config
    from elt_pipeline.extract.sofascore_extractor import SofaScoreExtractor
    from elt_pipeline.extract.sofascore_endpoints import SofaScoreEndpoints
    from elt_pipeline.transform.sofascore_transformer import SofaScoreTransformer
    from utils.db_connector import DatabaseConnector # Import để kiểm tra kết nối DB nếu cần
    from dataclasses import asdict, is_dataclass
except ImportError as e:
    print(f"Lỗi import: {e}. Hãy đảm bảo bạn chạy script này từ thư mục gốc của dự án (ai-engine).")
    exit(1)


# --- Cấu hình ---
# Các tham số bạn có thể thay đổi để test
TARGET_SEASON_NAME = "2022/23"
NUM_RANDOM_MATCHES_TO_TEST = 3 # Số trận ngẫu nhiên để test chi tiết
OUTPUT_DIR = Path(__file__).parent / "output_test_results"


# --- Các hàm Helper ---

def setup_logging():
    """Cấu hình logging để hiển thị thông tin chi tiết."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    # Giảm nhiễu từ các thư viện cấp thấp
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("curl_cffi").setLevel(logging.WARNING)

def save_to_json(data, filename, output_dir=OUTPUT_DIR):
    """Lưu dữ liệu vào file JSON một cách an toàn."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / filename
        
        # Hàm đặc biệt để xử lý các object không thể serialize mặc định
        def json_default_serializer(obj):
            # Sửa lỗi: Kiểm tra từng loại một một cách tường minh
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, Path):
                return str(obj)
            if isinstance(obj, Enum):
                return obj.value
            if is_dataclass(obj):
                return asdict(obj)

            # Nếu không phải các loại trên, báo lỗi rõ ràng
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        with open(filepath, 'w', encoding='utf-8') as f:
            # Truyền hàm serializer vào json.dump
            json.dump(data, f, ensure_ascii=False, indent=4, default=json_default_serializer)
        
        logging.info(f"Đã lưu dữ liệu thành công vào: {filepath}")
        return True
    except Exception as e:
        logging.error(f"Lỗi khi lưu file JSON '{filename}': {e}", exc_info=True)
        return False

# --- Hàm chính thực thi luồng test ---

def main():
    start_time = time.time()
    setup_logging()
    logger = logging.getLogger("IntegrationTest")
    
    print("=" * 60)
    logger.info("BẮT ĐẦU KỊCH BẢN KIỂM THỬ TÍCH HỢP (EXTRACT & TRANSFORM - PHIÊN BẢN ĐẦY ĐỦ)")
    print("=" * 60)

    # --- 1. Giai đoạn CONFIG ---
    logger.info("1. Tải cấu hình hệ thống...")
    try:
        config = get_config()
        sofascore_config = config.sofascore
        scraping_config = config.scraping
        logger.info("Tải cấu hình thành công.")
    except Exception as e:
        logger.critical(f"Không thể tải cấu hình. Dừng test. Lỗi: {e}", exc_info=True)
        return

    # --- 2. Giai đoạn EXTRACT (Lấy danh sách trận đấu) ---
    extractor = SofaScoreExtractor(sofascore_config, scraping_config)
    transformer = SofaScoreTransformer()
    
    try:
        logger.info("-" * 60)
        season_id_map = sofascore_config.get_season_id_mapping()
        target_season_id = season_id_map.get(TARGET_SEASON_NAME)

        if not target_season_id:
            logger.critical(f"Không tìm thấy Season ID cho '{TARGET_SEASON_NAME}' trong cấu hình.")
            return

        logger.info(f"2. Bắt đầu lấy danh sách các trận đấu cho mùa giải {TARGET_SEASON_NAME} (ID: {target_season_id})...")
        
        all_matches_raw, _ = extractor.fetch_paginated_data(
            endpoint=SofaScoreEndpoints.SEASON_MATCHES_LAST,
            response_field="events",
            tournament_id=sofascore_config.premier_league_id,
            season_id=target_season_id
        )

        if not all_matches_raw:
            logger.error("Không lấy được danh sách trận đấu nào từ API. Dừng test.")
            return

        logger.info(f"Lấy thành công danh sách {len(all_matches_raw)} trận đấu thô.")
        save_to_json(all_matches_raw, f"raw_matches_{TARGET_SEASON_NAME.replace('/', '-')}.json")
        
        # --- 3. Giai đoạn EXTRACT & TRANSFORM (Chi tiết từng trận - Đầy đủ) ---
        logger.info("-" * 60)
        logger.info(f"3. Chọn ngẫu nhiên {NUM_RANDOM_MATCHES_TO_TEST} trận để xử lý chi tiết (lấy đầy đủ dữ liệu)...")

        matches_to_test = random.sample(all_matches_raw, min(len(all_matches_raw), NUM_RANDOM_MATCHES_TO_TEST))

        successful_transforms = 0
        failed_transforms = 0

        for i, match_summary in enumerate(matches_to_test):
            match_id = match_summary.get("id")
            home_team_name = match_summary.get("homeTeam", {}).get("name", "N/A")
            away_team_name = match_summary.get("awayTeam", {}).get("name", "N/A")
            
            print("\n" + "-" * 20 + f" Test Case {i+1}/{len(matches_to_test)} " + "-" * 20)
            logger.info(f"Đang xử lý trận: {home_team_name} vs {away_team_name} (ID: {match_id})")

            try:
                # 3.1. Extract chi tiết - LẤY TẤT CẢ DỮ LIỆU LIÊN QUAN
                logger.info(f"   -> Extracting ALL details (match, incidents, lineups, stats)...")
                
                match_details_raw = extractor.fetch_match_detail(match_id=match_id)
                incidents_raw = extractor.fetch_incidents(match_id=match_id)
                lineups_raw = extractor.fetch_lineups(match_id=match_id)
                statistics_raw = extractor.fetch_statistics(match_id=match_id)

                if not match_details_raw:
                    logger.error(f"   !!! Lỗi: Không lấy được chi tiết trận đấu ID {match_id}. Bỏ qua.")
                    failed_transforms += 1
                    continue
                
                # Lưu tất cả dữ liệu thô để gỡ lỗi nếu cần
                raw_data_bundle = {
                    "details": match_details_raw,
                    "incidents": incidents_raw,
                    "lineups": lineups_raw,
                    "statistics": statistics_raw
                }
                save_to_json(raw_data_bundle, f"raw_bundle_match_{match_id}.json")
                
                # 3.2. Transform - Bây giờ Transformer sẽ nhận tất cả dữ liệu
                # (Lưu ý: Transformer hiện tại của bạn chưa sử dụng lineups và statistics,
                # nhưng việc truyền vào cho thấy luồng dữ liệu đã hoàn chỉnh)
                logger.info(f"   -> Transforming data...")
                parsed_match = transformer.transform_match_and_events(
                    raw_match_data=match_details_raw.get("event", {}),
                    raw_events=incidents_raw.get("incidents", []) if incidents_raw else []
                    # Khi bạn nâng cấp Transformer, bạn có thể truyền thêm:
                    # raw_lineups=lineups_raw,
                    # raw_statistics=statistics_raw
                )

                if parsed_match:
                    logger.info(f"   => Thành công! Đã transform thành object ParsedMatch.")
                    save_to_json(parsed_match, f"transformed_match_{match_id}.json")
                    successful_transforms += 1
                else:
                    logger.error(f"   !!! Lỗi: Transformer trả về None cho trận đấu ID {match_id}. Kiểm tra log để biết chi tiết.")
                    failed_transforms += 1

            except Exception as e:
                logger.error(f"   !!! Lỗi không mong muốn khi xử lý trận đấu ID {match_id}: {e}", exc_info=True)
                failed_transforms += 1

    finally:
        if 'extractor' in locals() and extractor:
            extractor.close()
        
        end_time = time.time()
        logger.info("-" * 60)
        logger.info("BÁO CÁO KẾT QUẢ KIỂM THỬ TÍCH HỢP")
        logger.info(f"Tổng thời gian thực hiện: {end_time - start_time:.2f} giây")
        if 'successful_transforms' in locals():
            logger.info(f"Số trận được chọn để test chi tiết: {len(matches_to_test)}")
            logger.info(f"   - Transform thành công: {successful_transforms}")
            logger.info(f"   - Transform thất bại: {failed_transforms}")
        logger.info(f"Kết quả chi tiết đã được lưu vào thư mục: {OUTPUT_DIR.resolve()}")
        print("=" * 60)
        logger.info("KỊCH BẢN KIỂM THỬ TÍCH HỢP KẾT THÚC")
        print("=" * 60)

if __name__ == "__main__":
    main()