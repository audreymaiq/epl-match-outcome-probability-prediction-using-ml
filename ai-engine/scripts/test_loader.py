# ai_engine/scripts/test_loader.py
import json
import os
import sys
from datetime import datetime
from dateutil.parser import isoparse

from ._test_helper import setup_test_environment
setup_test_environment()

from utils.db_connector import DatabaseConnector
from elt_pipeline.load.sofascore_loader import SofaScoreLoader
from elt_pipeline.transform.data_structures import *

# --- CONFIG ---
SAMPLE_DATA_DIR = "test_data"
PARSED_FILE = os.path.join(SAMPLE_DATA_DIR, 'sample_parsed_match.json')

def dict_to_parsed_match(data: dict) -> ParsedMatch:
    """
    Helper để tái tạo object ParsedMatch lồng nhau từ một dict.
    """
    try:
        # 1. Tái tạo các object từ trong ra ngoài
        
        # Tái tạo League
        league_data = data['season']['league']
        league = ParsedLeague(**league_data)

        # Tái tạo Season (và gán object league đã tạo)
        season_data = data['season']
        season = ParsedSeason(
            name=season_data['name'],
            start_year=season_data['start_year'],
            end_year=season_data['end_year'],
            league=league # Gán object league vào đây
        )
        
        # Tái tạo các object khác
        home_team = ParsedTeam(**data['home_team'])
        away_team = ParsedTeam(**data['away_team'])
        stadium = ParsedStadium(**data['stadium']) if data.get('stadium') else None
        referee = ParsedReferee(**data['referee']) if data.get('referee') else None
        
        # 2. Xóa các key đã được xử lý dưới dạng object lồng nhau
        # để tránh lỗi "unexpected keyword argument" khi khởi tạo ParsedMatch
        data.pop('season', None)
        data.pop('home_team', None)
        data.pop('away_team', None)
        data.pop('stadium', None)
        data.pop('referee', None)

        # 3. Chuyển đổi datetime và tạo object ParsedMatch cuối cùng
        data['match_datetime'] = isoparse(data['match_datetime'])
        
        # 4. Tạo object chính, truyền vào cả các giá trị gốc và các object đã tái tạo
        return ParsedMatch(
            **data,
            season=season,
            home_team=home_team,
            away_team=away_team,
            stadium=stadium,
            referee=referee
        )
    except KeyError as e:
        print(f"Error reconstructing dataclass: Missing key {e}")
        raise

def main():
    print("--- Running Test: Loader ---")

    if not os.path.exists(PARSED_FILE):
        print(f"FAILED: Parsed data file not found at '{PARSED_FILE}'.")
        print("   -> Please run 'python -m ai_engine.scripts.test_transformer' first.")
        sys.exit(1)

    with open(PARSED_FILE, 'r', encoding='utf-8') as f:
        parsed_dict = json.load(f)

    # Tái tạo object ParsedMatch từ dict
    parsed_match = dict_to_parsed_match(parsed_dict)
    
    print("\nChecking database connection...")
    if not DatabaseConnector.check_connection():
        print("FAILED: Cannot connect to the test database. Check your .env.test settings.")
        sys.exit(1)
    print("   -> Connection successful.")

    try:
        print("\nAttempting to load one match in a transaction...")
        with DatabaseConnector.session_scope() as session:
            loader = SofaScoreLoader(session)
            internal_id = loader.load_full_match_data(parsed_match)
            if not internal_id:
                raise RuntimeError("load_full_match_data returned None")

        print(f"SUCCESS: Loaded match with internal_id={internal_id}.")
        print("   -> Transaction committed. Please check your database tables:")
        print("      'Leagues', 'Seasons', 'Teams', 'Matches', 'ExternalMapping'")

    except Exception as e:
        print(f"FAILED: An error occurred during loading. Transaction was rolled back.")
        print(f"   -> Error: {e}")
        sys.exit(1)

    print("\n--- Test Loader: FINISHED ---")

if __name__ == "__main__":
    main()