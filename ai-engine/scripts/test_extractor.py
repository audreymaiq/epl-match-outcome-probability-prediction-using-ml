# ai_engine/scripts/test_extractor.py
import json
import os
import sys
from pprint import pprint

# Thiết lập môi trường trước khi import các module của dự án
from ._test_helper import setup_test_environment
setup_test_environment()

# Giờ mới import các module khác
from config.settings import get_config
from elt_pipeline.extract.sofascore_extractor import SofaScoreExtractor
import requests_cache

# --- CONFIG ---
# Lấy một ID trận đấu thật từ trang SofaScore
TEST_MATCH_ID = 12436536 # Ví dụ: Man City vs West Ham 19/05/2024
SAMPLE_DATA_DIR = "test_data"
os.makedirs(SAMPLE_DATA_DIR, exist_ok=True)

def main():
    print("--- Running Test: Extractor ---")
    
    # Kích hoạt cache
    requests_cache.install_cache('test_cache', expire_after=3600) # Cache trong 1 giờ
    print("Requests Caching: ENABLED for this test.")

    config = get_config()
    extractor = SofaScoreExtractor(config.sofascore, config.scraping)
    
    success = True
    try:
        print(f"\nFetching detail for match_id={TEST_MATCH_ID}...")
        detail_data = extractor.fetch_match_detail(TEST_MATCH_ID)

        if not detail_data:
            print("FAILED: fetch_match_detail returned None.")
            success = False
        else:
            print("SUCCESS: Fetched match detail.")
            # Lưu dữ liệu mẫu để test_transformer có thể dùng
            output_path = os.path.join(SAMPLE_DATA_DIR, 'sample_detail.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(detail_data, f, ensure_ascii=False, indent=2)
            print(f"   -> Sample data saved to '{output_path}'")
            
            print("\nSample of fetched data:")
            pprint({k: v for k, v in detail_data.items() if k in ['id', 'startTimestamp', 'homeTeam', 'awayTeam', 'status']})

    except Exception as e:
        print(f"CRITICAL FAILURE during extraction: {e}")
        success = False
    finally:
        extractor.close()
        requests_cache.uninstall_cache()
        print("\nRequests Caching: DISABLED.")

    print("\n--- Test Extractor: FINISHED ---")
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()