# scripts/test_settings.py

import os
import sys
from pathlib import Path

# 1. Thêm đường dẫn dự án
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 2. Import các module của dự án
from config.settings import get_config
from utils.db_connector import DatabaseConnector
import logging

# Kiểm tra ngay lập tức xem biến đã được nạp chưa
print(f"[PRE-CHECK] DB_USER in os.environ: {os.getenv('DB_USER')}")
print(f"[PRE-CHECK] DB_PASSWORD in os.environ: {'*' * len(os.getenv('DB_PASSWORD', '')) if os.getenv('DB_PASSWORD') else 'EMPTY'}")

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    log = logging.getLogger("test_settings")
    log.info("Đang khởi tạo ConfigManager...")
    cfg = get_config()

    # === Database ===
    print("\n[Database Settings]")
    print(f"DSN: {cfg.db.dsn}")
    print(f"Is configured: {cfg.db.is_configured}")

    # === API-Football ===
    # print("\n[API-Football Settings (Legacy)]")
    # print(f"Base URL: {cfg.api.base_url}")
    # print(f"Available keys: {len(cfg.api.api_keys)} keys")
    # print(f"Random key: {cfg.api.get_random_key()[:10]}...")
    # print(f"Is configured: {cfg.api.is_configured}")

    # === Sofascore ===
    print("\n[Sofascore Settings]")
    print(f"Base URL: {cfg.sofascore.base_url}")
    print(f"EPL ID: {cfg.sofascore.premier_league_id}")
    print(f"Rate limit: {cfg.sofascore.requests_per_minute} req/min")
    print(f"Delay: {cfg.sofascore.delay_between_requests} seconds")
    print(f"Max retries: {cfg.sofascore.max_retries}")
    print(f"User agents: {len(cfg.sofascore.user_agents)} available")
    print(f"Sample headers keys: {list(cfg.sofascore.get_headers().keys())}")
    print(f"Is configured: {cfg.sofascore.is_configured}")

    # === Scraping ===
    print("\n[Scraping Settings]")
    print(f"Request timeout: {cfg.scraping.request_timeout} seconds")
    print(f"Max retries: {cfg.scraping.max_retries}")
    print(f"Delay between requests: {cfg.scraping.delay_between_requests} seconds")
    print(f"Concurrent requests: {cfg.scraping.concurrent_requests}")
    print(f"Proxy list: {len(cfg.scraping.proxy_urls)} proxies")
    print(f"Rotate proxies: {cfg.scraping.rotate_proxies}")
    print(f"Enable JS: {cfg.scraping.enable_javascript}")
    print(f"Enable cache: {cfg.scraping.enable_cache}")
    print(f"Cache TTL: {cfg.scraping.cache_ttl} seconds")
    print(f"Is configured: {cfg.scraping.is_configured}")

    # === Season ===
    print("\n[Season Settings]")
    print(f"Current season: {cfg.seasons.current_season}")
    print(f"Last completed: {cfg.seasons.last_completed_season}")
    print(f"Latest season: {cfg.seasons.latest_season}")
    print(f"Timezone: {cfg.seasons.timezone}")
    print(f"Supported seasons: {len(cfg.seasons.supported_seasons)} seasons")
    for y, name in cfg.seasons.supported_seasons.items():
        print(f"  {y}: {name}")
    seasons_to_fetch = cfg.seasons.get_seasons_to_fetch()
    print(f"Seasons to fetch ({len(seasons_to_fetch)} years): {seasons_to_fetch}")

    # === DB Connection Test ===
    print("\n[Database Connection Test]")
    try:
        if DatabaseConnector.check_connection():
            print("Database connected successfully")
        else:
            print("Database connection failed (check_connection returned False)")
    except Exception as e:
        print(f"Database connection failed with exception: {e}")

    # === Environment Info ===
    print("\n[Environment Info]")
    print(f"Is production: {cfg.is_production}")
    print(f"Is development: {cfg.is_development}")
    print("\nConfiguration loaded successfully!")


if __name__ == "__main__":
    main()
