# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Cấu hình database
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'premier_league'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}

# ------------------------------------------------------------------------
# Cấu hình API
# config.py (bổ sung)
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Hàm refresh API keys
def refresh_api_keys():
    return os.getenv('API_FOOTBALL_KEY', '').split(',')

# Sử dụng hàm để khởi tạo
API_FOOTBALL_CONFIG = {
    'api_key': refresh_api_keys(),  # Sẽ gọi hàm khi khởi động
    'base_url': os.getenv('API_BASE_URL', 'https://v3.football.api-sports.io'),
    'last_refresh': datetime.now()
}

# Có thể thêm hàm để refresh khi cần
def refresh_config():
    API_FOOTBALL_CONFIG['api_key'] = refresh_api_keys()
    API_FOOTBALL_CONFIG['last_refresh'] = datetime.now()

# ------------------------------------------------------------------------
# Cấu hình mùa giải cần thu thập
SEASONS = [
    (2016, "2016/17"),
    (2017, "2017/18"),
    (2018, "2018/19"),
    (2019, "2019/20"),
    (2020, "2020/21"),
    (2021, "2021/22"),
    (2022, "2022/23")
]