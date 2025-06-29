# ai_engine/scripts/test_transformer.py
import json
import os
from pprint import pprint
import sys

from ._test_helper import setup_test_environment
setup_test_environment()

from elt_pipeline.transform.sofascore_transformer import SofaScoreTransformer

# --- CONFIG ---
SAMPLE_DATA_DIR = "test_data"
DETAIL_FILE = os.path.join(SAMPLE_DATA_DIR, 'sample_detail.json')

def main():
    print("--- Running Test: Transformer (Offline) ---")
    
    if not os.path.exists(DETAIL_FILE):
        print(f"FAILED: Sample data file not found at '{DETAIL_FILE}'.")
        print("   -> Please run 'python -m ai_engine.scripts.test_extractor' first.")
        sys.exit(1)
        
    with open(DETAIL_FILE, 'r', encoding='utf-8') as f:
        raw_detail = json.load(f)

    # Dùng cùng dữ liệu cho summary và detail để test
    raw_summary = raw_detail

    transformer = SofaScoreTransformer()
    
    print("\nTransforming sample data...")
    parsed_match = transformer.transform_match(raw_summary, raw_detail)

    if not parsed_match:
        print("FAILED: transform_match returned None.")
        sys.exit(1)
    
    print("SUCCESS: Transformed data into ParsedMatch object.")
    
    # Lưu object đã parse để test_loader có thể dùng
    # Chuyển dataclass thành dict để lưu JSON
    output_path = os.path.join(SAMPLE_DATA_DIR, 'sample_parsed_match.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        # Cần một helper để convert dataclass to dict
        import dataclasses
        json.dump(dataclasses.asdict(parsed_match), f, ensure_ascii=False, indent=2, default=str)
    print(f"   -> Parsed object saved to '{output_path}'")

    print("\nResulting ParsedMatch object:")
    pprint(parsed_match)

    print("\n--- Test Transformer: FINISHED ---")

if __name__ == "__main__":
    main()