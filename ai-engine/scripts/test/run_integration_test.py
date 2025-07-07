# scripts/run_integration_test.py

import logging
import json
import time
from datetime import date, datetime
from typing import Optional
from enum import Enum
from pathlib import Path
from decimal import Decimal

# --- Thiết lập môi trường và import ---
# Tự động thêm thư mục gốc của dự án vào sys.path để đảm bảo import thành công
# (Giả định file này nằm trong thư mục con của dự án)
project_root = Path(__file__).resolve().parent.parent.parent
import sys
sys.path.insert(0, str(project_root))

try:
    # Import các thành phần của hệ thống đã được chuẩn hóa
    from config.settings import get_config
    from elt_pipeline.extract.sofascore_extractor import SofaScoreExtractor
    from elt_pipeline.transform.sofascore_transformer import SofaScoreTransformer
    from elt_pipeline.transform.data_structures import ParsedMatchBundle 
    from dataclasses import asdict, is_dataclass
except ImportError as e:
    print(f"Lỗi import: {e}.")
    print(f"Đã thử thêm thư mục gốc vào path: {project_root}")
    print("Gợi ý: Hãy đảm bảo bạn đang chạy script này từ thư mục gốc của dự án (ví dụ: `python scripts/run_integration_test.py`)")
    exit(1)


# --- Cấu hình ---
# Để test nhanh và nhất quán, ta sẽ chỉ định một ID trận đấu cụ thể đã có dữ liệu
# Sử dụng ID trận Fulham vs Man City từ ví dụ của bạn
TARGET_MATCH_ID = 12436559
OUTPUT_DIR = project_root / "scripts" / "test_output" # Đảm bảo đường dẫn tương đối từ gốc


# --- Các hàm Helper ---

def setup_logging():
    """Cấu hình logging để hiển thị thông tin chi tiết."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logging.getLogger("httpx").setLevel(logging.WARNING) # Giảm nhiễu từ httpx

def json_default_serializer(obj):
    """Hàm đặc biệt để xử lý các object không thể serialize mặc định."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Decimal):
        # Chuyển Decimal thành float để JSON hóa, hoặc string để giữ nguyên độ chính xác
        return str(obj) 
    if is_dataclass(obj):
        return asdict(obj) # Xử lý các dataclass lồng nhau
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

def save_to_json(data, filename: str, output_dir=OUTPUT_DIR):
    """Lưu dữ liệu vào file JSON một cách an toàn."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            # Truyền hàm serializer đã được cập nhật
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
    
    print("=" * 70)
    logger.info("BẮT ĐẦU KỊCH BẢN KIỂM THỬ TÍCH HỢP CHO MỘT TRẬN ĐẤU DUY NHẤT")
    logger.info("(EXTRACT -> TRANSFORM -> BUNDLE)")
    print("=" * 70)

    # --- 1. Giai đoạn CONFIG & KHỞI TẠO ---
    logger.info("1. Tải cấu hình và khởi tạo các thành phần...")
    try:
        config = get_config()
        extractor = SofaScoreExtractor(config.sofascore, config.scraping)
        transformer = SofaScoreTransformer()
        logger.info("Tải cấu hình và khởi tạo thành công.")
    except Exception as e:
        logger.critical(f"Không thể khởi tạo hệ thống. Dừng test. Lỗi: {e}", exc_info=True)
        return

    # --- 2. Giai đoạn EXTRACT (Lấy toàn bộ dữ liệu cho một trận đấu) ---
    logger.info("-" * 70)
    logger.info(f"2. Bắt đầu EXTRACT toàn bộ dữ liệu cho trận đấu có ID: {TARGET_MATCH_ID}")
    
    raw_data_bundle = {}
    try:
        # Lấy TẤT CẢ các mảnh dữ liệu cần thiết
        match_details_raw = extractor.fetch_match_detail(match_id=TARGET_MATCH_ID)
        incidents_raw = extractor.fetch_incidents(match_id=TARGET_MATCH_ID)
        lineups_raw = extractor.fetch_lineups(match_id=TARGET_MATCH_ID)
        statistics_raw = extractor.fetch_statistics(match_id=TARGET_MATCH_ID)

        if not match_details_raw:
            logger.critical(f"Không thể lấy được dữ liệu chi tiết cho trận đấu ID {TARGET_MATCH_ID}. Dừng test.")
            return

        # Gom tất cả dữ liệu thô vào một "bundle" để lưu lại và truyền cho Transformer
        raw_data_bundle = {
            "details": match_details_raw,
            "incidents": incidents_raw,
            "lineups": lineups_raw,
            "statistics": statistics_raw
        }
        
        logger.info("Lấy dữ liệu thô thành công. Lưu lại để kiểm tra...")
        save_to_json(raw_data_bundle, f"raw_bundle_match_{TARGET_MATCH_ID}.json")

    except Exception as e:
        logger.critical(f"Lỗi nghiêm trọng trong quá trình EXTRACT. Dừng test. Lỗi: {e}", exc_info=True)
        return
    finally:
        extractor.close() # Đóng kết nối sau khi extract xong

    # --- 3. Giai đoạn TRANSFORM (Chuyển đổi toàn bộ bundle) ---
    logger.info("-" * 70)
    logger.info("3. Bắt đầu TRANSFORM toàn bộ raw bundle...")
    
    transformed_bundle: Optional[ParsedMatchBundle] = None
    try:
        # Gọi phương thức transform mới, truyền toàn bộ bundle thô
        transformed_bundle = transformer.transform_match_bundle(
            details=raw_data_bundle.get("details", {}),
            incidents=raw_data_bundle.get("incidents"),
            lineups=raw_data_bundle.get("lineups"),
            statistics=raw_data_bundle.get("statistics")
        )
        
        if transformed_bundle:
            logger.info("=> THÀNH CÔNG! Transformer đã xử lý và trả về một ParsedMatchBundle hoàn chỉnh.")
            
            # Kiểm tra nhanh một vài điểm dữ liệu quan trọng
            logger.info(f"   -> Trận đấu: {transformed_bundle.match.home_team.name} vs {transformed_bundle.match.away_team.name}")
            logger.info(f"   -> Tỷ số đã sửa: {transformed_bundle.match.home_goals} - {transformed_bundle.match.away_goals}")
            logger.info(f"   -> Số cầu thủ trong đội hình: {len(transformed_bundle.lineups)}")
            logger.info(f"   -> Số thống kê cầu thủ: {len(transformed_bundle.player_stats)}")
            logger.info(f"   -> Số thống kê đội: {len(transformed_bundle.team_stats)}")
            logger.info(f"   -> Số sự kiện (đã lọc): {len(transformed_bundle.events)}")
            
            save_to_json(transformed_bundle, f"transformed_bundle_match_{TARGET_MATCH_ID}.json")
        else:
            logger.critical("!!! THẤT BẠI: Transformer trả về None. Vui lòng kiểm tra log lỗi ở trên.")
            return

    except Exception as e:
        logger.critical(f"Lỗi nghiêm trọng trong quá trình TRANSFORM. Dừng test. Lỗi: {e}", exc_info=True)
        return

    # --- 4. Giai đoạn BÁO CÁO ---
    end_time = time.time()
    logger.info("-" * 70)
    logger.info("BÁO CÁO KẾT QUẢ KIỂM THỬ TÍCH HỢP")
    logger.info(f"Tổng thời gian thực hiện: {end_time - start_time:.2f} giây")
    if transformed_bundle:
        logger.info("Trạng thái: THÀNH CÔNG")
        logger.info("Đã thực hiện thành công chuỗi Extract -> Transform cho một trận đấu.")
    else:
        logger.info("Trạng thái: THẤT BẠI")

    logger.info(f"Kết quả chi tiết đã được lưu vào thư mục: {OUTPUT_DIR.resolve()}")
    print("=" * 70)
    logger.info("KỊCH BẢN KIỂM THỬ TÍCH HỢP KẾT THÚC")
    print("=" * 70)


if __name__ == "__main__":
    main()