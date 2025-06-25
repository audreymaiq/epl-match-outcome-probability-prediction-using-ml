# scripts/test_env_and_connections.py

import sys
from pathlib import Path

# 0. Thêm path tới ai-engine để Python tìm package
ROOT = Path(__file__).parent.parent  # ../ai-engine
sys.path.insert(0, str(ROOT))

# 1. Load env trước khi import ConfigManager
from config.env_loader import load_environment, EnvLoadError
try:
    load_environment(env_path="ai-engine/.env")
except EnvLoadError as e:
    print(f"EnvLoadError: {e}")
    sys.exit(1)

# 2. Bây giờ import mới an toàn
import logging
from config.settings import get_config, ConfigManager
from elt_pipeline.extract.api_football_client import APIFootballClient
from utils.db_connector import DatabaseConnector

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    log = logging.getLogger("test_env")

    # ---- 1. Validate ConfigManager ----
    log.info("Khởi tạo và validate ConfigManager…")
    try:
        cfg: ConfigManager = get_config()  # .env đã load, nên API key có thể lấy được
        _ = cfg.db.dsn
        _ = cfg.api.base_url
        _ = cfg.seasons.supported_seasons
        log.info("ConfigManager đã khởi tạo và validate thành công")
    except Exception as e:
        log.critical(f"Config validation failed: {e}")
        sys.exit(1)
    print(f"ConfigManager: {cfg.api.api_keys}")
    pass
    # ---- 2. Test API-Football ----
    log.info("Kiểm tra kết nối tới API-Football…")
    try:
        client = APIFootballClient()
        if client.test_connection():
            log.info("API-Football kết nối thành công")
        else:
            log.critical("API-Football test_connection() trả về False")
            sys.exit(1)
    except Exception as e:
        log.critical(f"Lỗi khi test API-Football: {e}")
        sys.exit(1)

    # # ---- 3. Test Database ----
    # log.info("Kiểm tra kết nối tới Database…")
    # try:
    #     ok = DatabaseConnector.check_connection()
    #     if ok:
    #         log.info("Database kết nối thành công")
    #     else:
    #         log.critical("DatabaseConnector.check_connection() trả về False")
    #         sys.exit(1)
    # except Exception as e:
    #     log.critical(f"Lỗi khi kiểm tra database: {e}")
    #     sys.exit(1)

    log.info("Tất cả kiểm tra môi trường và kết nối đều thành công!")

if __name__ == "__main__":
    main()
