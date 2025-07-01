# scripts/test_transformer.py

# --- Bước 1: Thiết lập môi trường NGAY TỪ ĐẦU ---
# Đảm bảo các import từ các thư mục khác hoạt động
try:
    from ._test_helper import setup_test_environment
    setup_test_environment()
except ImportError:
    # Nếu chạy trực tiếp file này, cần điều chỉnh sys.path thủ công
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# ----------------------------------------------------

import logging
import json
import os
import random
from dataclasses import is_dataclass, asdict

# --- Giờ đây các import này sẽ hoạt động trơn tru ---
from elt_pipeline.transform.sofascore_transformer import SofaScoreTransformer
from elt_pipeline.transform.data_structures import ParsedMatch

# --- Cấu hình và các hàm Helper ---

def setup_logging():
    """Cấu hình logging để hiển thị thông tin chi tiết từ transformer."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logging.getLogger("elt_pipeline.transform").setLevel(logging.INFO)

class DataclassJSONEncoder(json.JSONEncoder):
    """
    Encoder đặc biệt để serialize các object dataclass (lồng nhau) thành JSON.
    """
    def default(self, o):
        if is_dataclass(o):
            return asdict(o)
        # Chuyển đổi datetime thành chuỗi ISO 8601
        if hasattr(o, 'isoformat'):
            return o.isoformat()
        # Chuyển đổi Enum thành giá trị của nó
        if hasattr(o, 'value'):
            return o.value
        return super().default(o)

def load_json_file(filepath):
    """Đọc và trả về nội dung của một file JSON."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logging.info(f"Đã đọc thành công file: {filepath}")
        return data
    except FileNotFoundError:
        logging.error(f"Lỗi: Không tìm thấy file '{filepath}'.")
        return None
    except json.JSONDecodeError:
        logging.error(f"Lỗi: File '{filepath}' không phải là định dạng JSON hợp lệ.")
        return None
    except Exception as e:
        logging.error(f"Lỗi không mong muốn khi đọc file '{filepath}': {e}")
        return None

def save_to_json(data, filename, output_dir="output"):
    """Lưu dữ liệu vào file JSON sử dụng encoder đặc biệt."""
    try:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4, cls=DataclassJSONEncoder)
        
        logging.info(f"Đã lưu dữ liệu biến đổi thành công vào: {filepath}")
        return True
    except Exception as e:
        logging.error(f"Lỗi khi lưu file JSON đã biến đổi '{filename}': {e}")
        return False

def main():
    """Hàm chính để chạy kịch bản kiểm thử Transformer."""
    print("--- BẮT ĐẦU KỊCH BẢN KIỂM THỬ TRANSFORMER ---")

    setup_logging()
    logger = logging.getLogger(__name__)

    # --- ĐỊNH NGHĨA CÁC FILE ĐẦU VÀO ---
    input_dir = "output"
    matches_summary_file = os.path.join(input_dir, "premier_league_2022-23_matches.json")
    
    # +++ SỬA ĐỔI: CHỈ ĐỊNH ID CỤ THỂ ĐỂ TEST +++
    SPECIFIC_MATCH_ID_TO_TEST = 10385427
    
    logger.info("Đang khởi tạo SofaScoreTransformer với các quy tắc 'sofascore'...")
    try:
        transformer = SofaScoreTransformer(api_type='sofascore')
    except Exception as e:
        logger.error(f"Lỗi khi khởi tạo Transformer: {e}")
        return

    # --- ĐỌC DỮ LIỆU THÔ ---
    all_matches_summaries = load_json_file(matches_summary_file)
    if not all_matches_summaries:
        return

    # +++ SỬA ĐỔI: TÌM TRẬN ĐẤU CỤ THỂ THAY VÌ CHỌN NGẪU NHIÊN +++
    target_match_summary = next(
        (match for match in all_matches_summaries if match.get("id") == SPECIFIC_MATCH_ID_TO_TEST), 
        None
    )

    if not target_match_summary:
        logger.error(f"Không tìm thấy dữ liệu summary cho Match ID {SPECIFIC_MATCH_ID_TO_TEST} trong file '{matches_summary_file}'.")
        return

    home_team_name = target_match_summary.get("homeTeam", {}).get("name", "N/A")
    away_team_name = target_match_summary.get("awayTeam", {}).get("name", "N/A")
    
    print("-" * 50)
    logger.info(f"Sẽ kiểm thử biến đổi cho trận: {home_team_name} vs {away_team_name}")
    logger.info(f"Match ID: {SPECIFIC_MATCH_ID_TO_TEST}")
    print("-" * 50)

    # Tìm và đọc file chi tiết tương ứng với ID đã chỉ định
    match_detail_file = os.path.join(input_dir, f"match_details_{SPECIFIC_MATCH_ID_TO_TEST}.json")
    match_detail_data = load_json_file(match_detail_file)
    
    if not match_detail_data:
        logger.error(f"Lỗi nghiêm trọng: Không tìm thấy file detail bắt buộc '{match_detail_file}' để test.")
        return

    # Logic xử lý detail và events vẫn giữ nguyên sự linh hoạt
    raw_detail_data = match_detail_data.get("event", match_detail_data)
    raw_events_data = match_detail_data.get("incidents")

    # --- GỌI HÀM TRANSFORMER CỐT LÕI ---
    logger.info("Đang gọi transformer.transform_match_and_events()...")
    parsed_match: ParsedMatch = transformer.transform_match_and_events(
        raw_summary=target_match_summary,
        raw_detail=raw_detail_data,
        raw_events=raw_events_data
    )

    # --- KIỂM TRA VÀ IN KẾT QUẢ ---
    print("-" * 50)
    logger.info("--- KẾT QUẢ BIẾN ĐỔI ---")

    if parsed_match:
        logger.info("Biến đổi thành công! Dữ liệu đã được chuẩn hóa.")
        
        # In ra các thuộc tính quan trọng để kiểm tra
        print(f"  -> Match ID (đã biến đổi): {parsed_match.external_id}")
        print(f"  -> Mùa giải: {parsed_match.season.name} ({parsed_match.season.start_year}-{parsed_match.season.end_year})")
        print(f"  -> Vòng đấu: {parsed_match.match_week}")
        print(f"  -> Ngày giờ trận đấu: {parsed_match.match_datetime.strftime('%Y-%m-%d %H:%M:%S %Z') if parsed_match.match_datetime else 'N/A'}")
        print(f"  -> Đội nhà: {parsed_match.home_team.name} (ID: {parsed_match.home_team.external_id})")
        print(f"  -> Đội khách: {parsed_match.away_team.name} (ID: {parsed_match.away_team.external_id})")
        print(f"  -> Tỷ số: {parsed_match.home_goals} - {parsed_match.away_goals}")
        print(f"  -> Tỷ số H1: {parsed_match.half_time_home_goals} - {parsed_match.half_time_away_goals}")
        print(f"  -> Trạng thái (đã chuẩn hóa): {parsed_match.status.name} ({parsed_match.status.value})")
        print(f"  -> Kết quả (đã chuẩn hóa): {parsed_match.outcome.name} ({parsed_match.outcome.value})")
        print(f"  -> Sân vận động: {parsed_match.stadium.name if parsed_match.stadium else 'N/A'}")
        print(f"  -> Trọng tài: {parsed_match.referee.name if parsed_match.referee else 'N/A'}")
        print(f"  -> Số sự kiện đã biến đổi: {len(parsed_match.events)}")

        # --- LƯU KẾT QUẢ ĐÃ BIẾN ĐỔI RA FILE JSON ---
        output_filename = f"transformed_match_{parsed_match.external_id}.json"
        save_to_json(parsed_match, output_filename)

    else:
        logger.error("Biến đổi thất bại. Hãy kiểm tra các log lỗi ở trên để biết chi tiết.")

    print("\n--- KỊCH BẢN KIỂM THỬ TRANSFORMER KẾT THÚC ---")

if __name__ == "__main__":
    main()