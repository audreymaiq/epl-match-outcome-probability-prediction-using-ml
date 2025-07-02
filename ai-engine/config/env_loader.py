# ai-engine/config/env_loader.py

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, List

logger = logging.getLogger(__name__)

class EnvLoadError(Exception):
    """Lỗi khi tải hoặc kiểm tra biến môi trường."""
    pass

def load_environment(
    env_path: Optional[str] = None,
    required_vars: Optional[List[str]] = None,
    exit_on_missing: bool = False,
    override: bool = False
) -> Optional[Path]:
    """
    Tải biến môi trường từ file .env với cơ chế dự phòng linh hoạt và multi-environment.

    Args:
        env_path: Đường dẫn/tên file env cụ thể (nếu None, sẽ tìm theo ENV_FILE hoặc multi-env).
        required_vars: Danh sách biến bắt buộc. Mặc định chỉ kiểm API_FOOTBALL_KEY.
        Các biến có default hợp lệ (như DB_HOST, DB_NAME) nên validate trong ConfigManager.
        exit_on_missing: Nếu True, sys.exit(1) khi thiếu biến bắt buộc; nếu False, raise EnvLoadError.
        override: Nếu True, ghi đè biến OS env đã có; nếu False, chỉ load biến chưa tồn tại.

    Returns:
        Path đến file đã load thành công, hoặc None nếu không tìm thấy file nào.

    Raises:
        EnvLoadError: Khi thiếu biến bắt buộc và exit_on_missing=False.
    """
    # 1. Xác định môi trường hiện tại
    env_name = os.getenv("ENVIRONMENT", "development").strip().lower()
    logger.info(f"Chuẩn bị load cấu hình cho môi trường: {env_name}")

    # 2. Xác định danh sách file ứng viên
    if env_path:
        candidates = [env_path]
    else:
        # Multi-env: ưu tiên .env.<env_name>, rồi .env.local (override dev), rồi .env mặc định
        candidates = [
            f".env.{env_name}",  # Ví dụ: .env.production, .env.staging, .env.development
            ".env.local",        # File local override (thường không commit)
            ".env",              # File env mặc định
        ]

    # 3. Thiết lập biến bắt buộc mặc định
    # Chỉ kiểm biến không có default an toàn. Ví dụ API key thường không có default.
    if required_vars is None:
        required_vars = []

    # 4. Thứ tự thư mục tìm file env
    # Ưu tiên: project root, Docker/K8s secrets, user-level config, fallback module path.
    search_dirs = [
        Path.cwd(),                              # Project root
        Path("/run/secrets"),                    # Docker secrets mount
        Path("/etc/secrets"),                    # Hệ thống secrets
        Path.home() / ".config" / "ai-engine",   # User-level config (ví dụ ~/.config/ai-engine/.env)
        # Fallback: nếu chạy cwd khác, tìm relative từ project code base:
        Path(__file__).parent.parent.parent,     # Giả định thư mục project root 3 cấp: config/module/...
        Path(__file__).parent                    # Module directory (ít khi dùng, nhưng giữ fallback)
    ]
    # Loại bỏ trùng lặp (nếu Path.cwd() trùng với fallback...)
    unique_dirs: List[Path] = []
    for d in search_dirs:
        if d not in unique_dirs:
            unique_dirs.append(d)

    # 5. Tìm file và load
    candidates_to_load: List[Path] = []

    # Tìm tất cả các file hợp lệ theo thứ tự ưu tiên từ cụ thể -> chung
    for candidate_name in candidates: # ['.env.production', '.env.local', '.env']
        for base_dir in unique_dirs:
            path = base_dir / candidate_name
            if path.is_file() and os.access(path, os.R_OK):
                candidates_to_load.append(path)
                # Đã tìm thấy file ứng viên này, không cần tìm file cùng tên ở nơi khác
                break

    # loaded_path sẽ lưu file có ưu tiên cao nhất (file cụ thể nhất)
    loaded_path: Optional[Path] = candidates_to_load[0] if candidates_to_load else None

    overall_success = False
    for path in reversed(candidates_to_load):
        # Luôn override để file cụ thể hơn ghi đè lên file chung chung
        success = load_dotenv(dotenv_path=path, override=True) 
        if success:
            logger.info(f"Đã tải và áp dụng biến môi trường từ: {path}")
            overall_success = True
        else:
            logger.warning(f"Tìm thấy file env tại {path} nhưng không load được nội dung.")    

    # 6. Log kết quả tìm file
    if not candidates_to_load:
        logger.info("Không tìm thấy file .env nào trong các thư mục tìm kiếm")
    elif not overall_success:
        # Tìm thấy file nhưng load thất bại hoặc không chứa biến valid
        logger.warning("Tìm thấy file .env nhưng không load được nội dung hợp lệ")

    # 7. Kiểm tra biến bắt buộc
    missing_vars: List[str] = []
    for var in required_vars:
        val = os.getenv(var)
        if val is None or (isinstance(val, str) and not val.strip()):
            missing_vars.append(var)

    if missing_vars:
        msg = f"Thiếu biến môi trường bắt buộc: {', '.join(missing_vars)}"
        logger.critical(msg)
        # Xác định production qua env_name
        is_production = env_name in ["production", "prod"]
        if is_production or exit_on_missing:
            logger.critical("Thoát chương trình do thiếu biến quan trọng")
            sys.exit(1)
        else:
            raise EnvLoadError(msg)

    # 8. Log thông tin nguồn cấu hình
    source = str(loaded_path) if loaded_path else "biến hệ thống"
    logger.info(f"Môi trường: {env_name} | Nguồn cấu hình: {source}")

    # 9. Cảnh báo nếu đang chạy development mà không có file .env
    if env_name == "development" and not loaded_path:
        logger.warning("Đang chạy development mà không có file .env - không khuyến nghị lâu dài")

    return loaded_path