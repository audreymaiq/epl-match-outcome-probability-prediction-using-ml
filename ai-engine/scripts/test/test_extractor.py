# ai-engine\scripts\test\test_extractor.py

# --- Bước 1: Thiết lập môi trường NGAY TỪ ĐẦU ---
from scripts.test._test_helper import setup_test_environment
setup_test_environment()
# ----------------------------------------------------

import logging
import json
import os
from datetime import datetime
from pybreaker import CircuitBreaker
import random

# Giờ đây các import này sẽ hoạt động trơn tru
from config.settings import SofascoreSettings, ScrapingSettings
from elt_pipeline.extract.sofascore_extractor import SofaScoreExtractor
from elt_pipeline.extract.sofascore_endpoints import SofaScoreEndpoints

def setup_logging():
    """Cấu hình logging để hiển thị thông tin chi tiết từ extractor."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("curl_cffi").setLevel(logging.WARNING)

#  Hàm helper để lưu file JSON ---
def save_to_json(data, filename, output_dir=None):
    """Lưu dữ liệu vào file JSON trong một thư mục chỉ định."""
    try:
        if output_dir is None:
            # Lấy đường dẫn tuyệt đối tới thư mục scripts/test/
            current_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(current_dir, "output_test")

        os.makedirs(output_dir, exist_ok=True)
        
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        logging.info(f"Đã lưu dữ liệu thành công vào file: {filepath}")
        return True
    except Exception as e:
        logging.error(f"Lỗi khi lưu file JSON '{filename}': {e}")
        return False

def main():
    """Hàm chính để chạy kịch bản kiểm thử."""
    print("--- BẮT ĐẦU KỊCH BẢN KIỂM THỬ EXTRACTOR ---")

    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Đang tải cấu hình (từ .env.test)...")
    try:
        sofascore_config = SofascoreSettings()
        scraping_config = ScrapingSettings()
    except Exception as e:
        logger.error(f"Lỗi khi tải cấu hình: {e}")
        return

    main_breaker = CircuitBreaker(fail_max=scraping_config.max_retries, reset_timeout=60)
    
    extractor = None
    try:
        logger.info("Đang khởi tạo SofaScoreExtractor...")
        extractor = SofaScoreExtractor(
            sofascore_config=sofascore_config,
            scraping_config=scraping_config
        )

        target_tournament_id = sofascore_config.premier_league_id
        target_season_name = "2022/23"
        season_id_mapping = sofascore_config.get_season_id_mapping()
        target_season_id = season_id_mapping.get(target_season_name)

        if not target_season_id:
            logger.error(f"Không tìm thấy ID cho mùa giải '{target_season_name}'.")
            return

        print("-" * 50)
        logger.info(f"Mục tiêu: Kéo dữ liệu các trận đấu của giải Ngoại hạng Anh")
        logger.info(f"Mùa giải: {target_season_name} (ID: {target_season_id})")
        print("-" * 50)
        
        target_endpoint = SofaScoreEndpoints.SEASON_MATCHES_LAST
        logger.info(f"Sẽ sử dụng endpoint: {target_endpoint.name}")

        all_matches, num_requests = extractor.fetch_paginated_data(
            endpoint=target_endpoint,
            breaker=main_breaker,
            tournament_id=target_tournament_id,
            season_id=target_season_id
        )

        print("-" * 50)
        logger.info("--- KẾT QUẢ KÉO DỮ LIỆU ---")
        
        if all_matches:
            logger.info(f"Thành công! Tìm thấy tổng cộng {len(all_matches)} trận đấu.")
            logger.info(f"Số lượng request đã thực hiện: {num_requests}")
            
            # Lưu danh sách tất cả các trận đấu vào file JSON ---
            season_filename_safe = target_season_name.replace('/', '-')
            matches_filename = f"premier_league_{season_filename_safe}_matches.json"
            save_to_json(all_matches, matches_filename)
            
            # Lấy 1 trận ngẫu nhiên để test lấy chi tiết
            random_match = random.choice(all_matches)
            match_id = random_match.get('id')
            home_team = random_match.get('homeTeam', {}).get('name', 'N/A')
            away_team = random_match.get('awayTeam', {}).get('name', 'N/A')
            
            logger.info(f"\nBây giờ sẽ test lấy chi tiết cho trận: {home_team} vs {away_team} (ID: {match_id})")
            
            match_details = extractor.fetch_match_detail(match_id=match_id, breaker=main_breaker)
            if match_details:
                logger.info("Lấy chi tiết trận đấu thành công!")
                
                # Lưu chi tiết trận đấu này vào file JSON ---
                details_filename = f"match_details_{match_id}.json"
                save_to_json(match_details, details_filename)

                venue = match_details.get('event', {}).get('venue', {}).get('stadium', {}).get('name', 'N/A')
                print(f"  -> Sân vận động: {venue}")
            else:
                logger.warning("Không lấy được chi tiết trận đấu.")

        else:
            logger.warning("Không kéo được dữ liệu nào. Hãy kiểm tra các thông báo lỗi ở trên.")

    except Exception as e:
        logger.error(f"Một lỗi không mong muốn đã xảy ra: {e}", exc_info=True)
    finally:
        if extractor:
            extractor.close()
        print("\n--- KỊCH BẢN KIỂM THỬ KẾT THÚC ---")

if __name__ == "__main__":
    main()