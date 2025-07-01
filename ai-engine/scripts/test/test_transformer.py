# ai-engine\scripts\test\test_transformer.py

# --- Bước 1: Thiết lập môi trường NGAY TỪ ĐẦU ---
import sys
import os
import copy 
try:
    from ._test_helper import setup_test_environment
    setup_test_environment()
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import logging
import json
from dataclasses import is_dataclass, asdict

# --- Import các thành phần đã được cập nhật ---
from elt_pipeline.transform.sofascore_transformer import SofaScoreTransformer
from elt_pipeline.transform.data_structures import ParsedMatch
from utils.dict_helpers import deep_merge_dicts # <<< BỔ SUNG IMPORT

# --- Cấu hình và các hàm Helper (giữ nguyên) ---

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logging.getLogger("elt_pipeline.transform").setLevel(logging.INFO)

class DataclassJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if is_dataclass(o):
            return asdict(o)
        if hasattr(o, 'isoformat'):
            return o.isoformat()
        if hasattr(o, 'value'):
            return o.value
        return super().default(o)

def get_output_dir():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, "output_test")

def save_to_json(data, filename, output_dir=None):
    try:
        if output_dir is None: output_dir = get_output_dir()
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4, cls=DataclassJSONEncoder)
        logging.info(f"Đã lưu dữ liệu biến đổi thành công vào: {filepath}")
        return True
    except Exception as e:
        logging.error(f"Lỗi khi lưu file JSON '{filename}': {e}")
        return False

def load_json_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logging.info(f"Đã đọc thành công file: {filepath}")
        return data
    except Exception as e:
        logging.error(f"Lỗi khi đọc file '{filepath}': {e}", exc_info=True)
        return None

def main():
    print("--- BẮT ĐẦU KỊCH BẢN KIỂM THỬ TRANSFORMER (PHIÊN BẢN ĐÃ SỬA) ---")
    setup_logging()
    logger = logging.getLogger(__name__)

    # --- INPUT ---
    input_dir = get_output_dir()
    matches_summary_file = os.path.join(input_dir, "premier_league_2022-23_matches.json")
    SPECIFIC_MATCH_ID_TO_TEST = 10385544

    logger.info("Đang khởi tạo SofaScoreTransformer...")
    try:
        transformer = SofaScoreTransformer(api_type='sofascore')
    except Exception as e:
        logger.error(f"Lỗi khi khởi tạo Transformer: {e}", exc_info=True)
        return

    all_matches_summaries = load_json_file(matches_summary_file)
    if not all_matches_summaries: return

    target_match_summary = next(
        (match for match in all_matches_summaries if match.get("id") == SPECIFIC_MATCH_ID_TO_TEST), None
    )
    if not target_match_summary:
        logger.error(f"Không tìm thấy dữ liệu summary cho Match ID {SPECIFIC_MATCH_ID_TO_TEST}.")
        return

    home_team_name = target_match_summary.get("homeTeam", {}).get("name", "N/A")
    away_team_name = target_match_summary.get("awayTeam", {}).get("name", "N/A")

    print("-" * 50)
    logger.info(f"Sẽ kiểm thử biến đổi cho trận: {home_team_name} vs {away_team_name} (ID: {SPECIFIC_MATCH_ID_TO_TEST})")
    print("-" * 50)

    # Load dữ liệu chi tiết
    match_detail_file = os.path.join(input_dir, f"match_details_{SPECIFIC_MATCH_ID_TO_TEST}.json")
    match_detail_full_data = load_json_file(match_detail_file)
    if not match_detail_full_data:
        logger.error(f"Không tìm thấy file detail bắt buộc: {match_detail_file}")
        return

    # Trích xuất các phần cần thiết
    # Dữ liệu chi tiết của trận đấu nằm trong key 'event'
    raw_detail_data = match_detail_full_data.get("event", match_detail_full_data)
    # Dữ liệu sự kiện nằm trong key 'incidents'
    raw_events_data = match_detail_full_data.get("incidents")

    logger.info("Hợp nhất dữ liệu summary và detail trước khi transform...")

    merged_match_data = deep_merge_dicts(copy.deepcopy(target_match_summary), copy.deepcopy(raw_detail_data))
    
    logger.info("Đang gọi transformer.transform_match_and_events() với dữ liệu đã hợp nhất...")
    parsed_match: ParsedMatch = transformer.transform_match_and_events(
        raw_match_data=merged_match_data,
        raw_events=raw_events_data
    )

    print("-" * 50)
    logger.info("--- KẾT QUẢ BIẾN ĐỔI ---")

    if parsed_match:
        logger.info("Biến đổi thành công! Dữ liệu đã được chuẩn hóa.")
        
        # In ra các thông tin chi tiết để kiểm tra
        print(f"  -> Match ID: {parsed_match.external_id}")
        print(f"  -> Mùa giải: {parsed_match.season.name}")
        print(f"  -> Đội nhà: {parsed_match.home_team.name} (Năm TL: {parsed_match.home_team.established_year})")
        print(f"  -> Đội khách: {parsed_match.away_team.name} (Năm TL: {parsed_match.away_team.established_year})")
        print(f"  -> Tỷ số: {parsed_match.home_goals}-{parsed_match.away_goals}")
        print(f"  -> Kết quả (chuẩn hóa): {parsed_match.outcome.name if parsed_match.outcome else 'N/A'}")
        print(f"  -> Sân vận động: {parsed_match.stadium.name if parsed_match.stadium else 'N/A'}")
        print(f"  -> Khán giả: {parsed_match.attendance}")
        print(f"  -> Trọng tài: {parsed_match.referee.name if parsed_match.referee else 'N/A'} (Quốc gia: {parsed_match.referee.country if parsed_match.referee else 'N/A'})")
        print(f"  -> Số sự kiện đã biến đổi: {len(parsed_match.events)}")

        if parsed_match.events:
            print(f"     -> Ví dụ sự kiện đầu tiên: Phút {parsed_match.events[0].minute}', Loại: {parsed_match.events[0].event_type.value}")

        output_filename = f"transformed_match_{parsed_match.external_id}.json"
        save_to_json(parsed_match, output_filename)
    else:
        logger.error("Biến đổi thất bại. Hãy kiểm tra các log lỗi ở trên để biết chi tiết.")

    print("\n--- KỊCH BẢN KIỂM THỬ TRANSFORMER KẾT THÚC ---")

if __name__ == "__main__":
    main()