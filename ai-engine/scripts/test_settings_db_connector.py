# scripts/test_settings.py

import os
import sys
from pathlib import Path

# 1. Thêm đường dẫn dự án
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 2. Thiết lập logging
from config.settings import get_config
from utils.db_connector import DatabaseConnector
import logging

# Kiểm tra ngay lập tức xem biến đã được nạp chưa
print(f"[PRE-CHECK] DB_USER in os.environ: {os.getenv('USER')}")
print(f"[PRE-CHECK] DB_PASSWORD in os.environ: {'*' * len(os.getenv('PASSWORD', '')) if os.getenv('PASSWORD') else 'EMPTY'}")

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
    try:
        if DatabaseConnector.check_connection():
            print("Database connection: SUCCESS")
        else:
            print("Database connection: FAILED (check_connection returned False)")
    except Exception as e:
        print(f"Database connection raised Exception: {e}")

    # === API-Football ===
    # print("\n[API-Football Settings (Legacy)]")
    # print(f"Base URL: {cfg.api.base_url}")
    # print(f"Available keys: {len(cfg.api.api_keys)} keys")
    # print(f"Random key: {cfg.api.get_random_key()[:10]}...")
    # print(f"Is configured: {cfg.api.is_configured}")

    # === Sofascore ===
    print("\n[Sofascore Settings]")
    print(f"Base URL: {cfg.sofascore.base_url}")
    print(f"Web Base URL: {cfg.sofascore.web_base_url}")
    print(f"Premier League ID: {cfg.sofascore.premier_league_id}")
    print(f"Rate Limit: {cfg.sofascore.requests_per_minute} req/min")
    print(f"Delay Between Requests: {cfg.sofascore.delay_between_requests}s")
    print(f"Retry Delay: {cfg.sofascore.retry_delay}s")
    print(f"User-Agents count: {len(cfg.sofascore.user_agents)}")
    print(f"Accept-Languages count: {len(cfg.sofascore.accept_languages)}")
    print(f"Sample headers: {cfg.sofascore.get_headers()}")
    print(f"Is configured: {cfg.sofascore.is_configured}")

    # === Scraping ===
    print("\n[Scraping Settings]")
    print(f"Timeout: {cfg.scraping.request_timeout}s")
    print(f"Retries: {cfg.scraping.max_retries}")
    print(f"Backoff factor: {cfg.scraping.backoff_factor}")
    print(f"Delay between requests: {cfg.scraping.delay_between_requests}s")
    print(f"Random delay range: {cfg.scraping.random_delay_range}")
    print(f"Concurrent requests: {cfg.scraping.concurrent_requests}")
    print(f"Enable JS: {cfg.scraping.enable_javascript}")
    print(f"Headless browser: {cfg.scraping.headless}")
    print(f"Browser type: {cfg.scraping.browser_type}")
    print(f"Proxies: {len(cfg.scraping.proxy_urls)} proxies")
    print(f"Rotate proxies: {cfg.scraping.rotate_proxies}")
    print(f"Enable cache: {cfg.scraping.enable_cache}")
    print(f"Cache TTL: {cfg.scraping.cache_ttl}s")
    print(f"Cache dir: {cfg.scraping.cache_dir}")
    print(f"Ignore robots.txt: {cfg.scraping.ignore_robots_txt}")
    print(f"Is configured: {cfg.scraping.is_configured}")
    if cfg.scraping.proxy_urls:
        print(f"Sample proxy: {cfg.scraping.get_random_proxy()}")
    print(f"Sample random delay: {cfg.scraping.get_random_delay():.2f}s")

    # === Season ===
    print("\n[Season Settings]")
    print(f"Timezone: {cfg.seasons.timezone}")
    print(f"Current season year start: {cfg.seasons.current_season_year_start}")
    print(f"Latest season: {cfg.seasons.latest_season}")
    print(f"Seasons to fetch: {cfg.seasons.seasons_to_fetch}")
    supported = cfg.seasons.supported_seasons
    print(f"Supported seasons ({len(supported)}):")
    for y, label in supported.items():
        print(f"  {y}: {label}")
    target_seasons = cfg.seasons.get_target_seasons()
    print(f"Target scrape seasons ({len(target_seasons)}): {target_seasons}")

    # === Environment Info ===
    print("\n[Environment Info]")
    print(f"Is production: {cfg.is_production}")
    print(f"Is development: {cfg.is_development}")
    print("\nConfiguration loaded successfully!")


if __name__ == "__main__":
    main()
