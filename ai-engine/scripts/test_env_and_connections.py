#!/usr/bin/env python3
# scripts/test_env_and_connections.py

import sys
import logging

# 1. Load env và get config
from config.env_loader import load_environment, EnvLoadError
from config.settings import get_config, ConfigManager

# 2. Test API-Football
from elt_pipeline.extract.api_football_client import APIFootballClient

# 3. Test Database
from utils.db_connector import DatabaseConnector

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    log = logging.getLogger("test_env")

    # ---- 1. Load .env và validate biến ----
    log.info("Bắt đầu load biến môi trường bằng EnvLoader…")
    try:
        loaded_path = load_environment()
        log.info(f"Đã load thành công file .env: {loaded_path}")
    except EnvLoadError as e:
        log.critical(f"EnvLoadError: {e}")
        sys.exit(1)
    except Exception as e:
        log.critical(f"Lỗi không lường trước khi load env: {e}")
        sys.exit(1)

    # ---- 2. Khởi tạo và validate toàn bộ config ----
    log.info("Khởi tạo ConfigManager và validate config…")
    try:
        # Lấy instance global
        cfg: ConfigManager = get_config()
        # Access các thuộc tính để trigger validation
        _ = cfg.db.dsn
        _ = cfg.api.base_url
        _ = cfg.seasons.supported_seasons
        log.info("ConfigManager đã khởi tạo và validate thành công")
    except Exception as e:
        log.critical(f"Config validation failed: {e}")
        sys.exit(1)

    # ---- 3. Test kết nối API-Football ----
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

    # ---- 4. Test kết nối Database ----
    log.info("Kiểm tra kết nối tới Database…")
    try:
        ok = DatabaseConnector.check_connection()
        if ok:
            log.info("Database kết nối thành công")
        else:
            log.critical("DatabaseConnector.check_connection() trả về False")
            sys.exit(1)
    except Exception as e:
        log.critical(f"Lỗi khi kiểm tra database: {e}")
        sys.exit(1)

    log.info("Tất cả kiểm tra môi trường và kết nối đều thành công!")

if __name__ == "__main__":
    main()
