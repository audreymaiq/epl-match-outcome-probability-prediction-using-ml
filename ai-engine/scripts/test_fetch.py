# ai-engine\scripts\test_fetch.py

import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
import argparse
import logging

from config.settings import get_config
from elt_pipeline.extract.sofascore_extractor import SofaScoreExtractor

# Argument parser để đọc log-level
parser = argparse.ArgumentParser()
parser.add_argument('--log-level', default='INFO', help='Set log level: DEBUG, INFO, WARNING, ERROR')
args = parser.parse_args()

logging.basicConfig(level=getattr(logging, args.log_level.upper()))

# Lấy một ID trận đấu thật từ trang SofaScore
TEST_MATCH_ID = 12436536 # Ví dụ: trận Bournemouth vs Leicester City 25/05/2024

config = get_config()
extractor = SofaScoreExtractor(config.sofascore, config.scraping)

print(f"Fetching summary for match {TEST_MATCH_ID}...")
# Giả sử API có endpoint lấy summary riêng
# Nếu không, bạn có thể tìm summary trong list events của một season

print(f"Fetching detail for match {TEST_MATCH_ID}...")
detail_data = extractor.fetch_match_detail(TEST_MATCH_ID)

if detail_data:
    with open('sample_match_detail.json', 'w', encoding='utf-8') as f:
        json.dump(detail_data, f, ensure_ascii=False, indent=4)
    print("Saved detailed data to sample_match_detail.json")

extractor.close()