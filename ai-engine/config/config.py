# config.py

import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# ------------------------- DATABASE CONFIG -------------------------------
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'premier_league'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}

# ------------------------- API CONFIG ------------------------------------
def refresh_api_keys():
    return os.getenv('API_FOOTBALL_KEY', '').split(',')

API_FOOTBALL_CONFIG = {
    'api_key': refresh_api_keys(),
    'base_url': os.getenv('API_BASE_URL', 'https://v3.football.api-sports.io'),
    'last_refresh': datetime.now()
}

def refresh_config():
    API_FOOTBALL_CONFIG['api_key'] = refresh_api_keys()
    API_FOOTBALL_CONFIG['last_refresh'] = datetime.now()

# ------------------------- SEASONS CONFIG --------------------------------
SEASONS = [
    (2016, "2016/17"),
    (2017, "2017/18"),
    (2018, "2018/19"),
    (2019, "2019/20"),
    (2020, "2020/21"),
    (2021, "2021/22"),
    (2022, "2022/23")
]

SEASON_YEAR_TO_NAME = {year: name for year, name in SEASONS}