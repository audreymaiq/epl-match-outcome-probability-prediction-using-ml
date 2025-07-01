# ai_engine/scripts/_test_helper.py
import os
import sys

def setup_test_environment():
    """
    Thiết lập môi trường để chạy các script test một cách chính xác.
    - Đặt biến môi trường để trỏ đến file .env.test
    - Thêm thư mục gốc của dự án vào sys.path để giải quyết import
    """
    # 1. Trỏ đến file cấu hình test
    # Hàm load_dotenv sẽ tìm thấy biến này và sử dụng file .env.test
    os.environ['ENV_FILE'] = '.env.test'
    
    # 2. Thêm thư mục gốc vào sys.path
    # Giả sử file này nằm trong ai-engine/scripts/
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    print("--- Test Environment Setup ---")
    print(f"Project Root: {project_root}")
    print(f"Using Env File: {os.environ['ENV_FILE']}")
    print("-" * 30)