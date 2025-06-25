# ai-engine\utils\logging_config.py

import logging
import logging.config
import os
import sys
from pathlib import Path
import datetime
from pythonjsonlogger import jsonlogger
import threading
from queue import Queue, Empty
import atexit

# Global setup flag
_LOGGING_SETUP = False
_log_queue = Queue(maxsize=1000)
_log_worker_thread = None
_log_listener = None


class SafeLogFormatter(jsonlogger.JsonFormatter):
    """JSON formatter với redaction thông tin nhạy cảm toàn diện"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sensitive_keywords = [
            "password", "api_key", "secret", "token", 
            "access_token", "auth_key", "credential"
        ]
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Thống nhất biến môi trường
        log_record["service"] = "premier-league-pipeline"
        log_record["environment"] = os.getenv("ENVIRONMENT", "unknown")
        log_record["host"] = os.getenv("HOSTNAME", "unknown")
        
        # Timestamp UTC chính xác
        log_record["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
        
        # Redact toàn bộ record
        self.redact_sensitive_data(log_record)
    
    def redact_sensitive_data(self, record):
        """Quét và redact thông tin nhạy cảm trong mọi trường log"""
        for key, value in list(record.items()):
            key_lower = key.lower()
            
            # Kiểm tra tên trường
            if any(kw in key_lower for kw in self.sensitive_keywords):
                record[key] = "***REDACTED***"
                continue
                
            # Kiểm tra giá trị trường
            if isinstance(value, str):
                value_lower = value.lower()
                if any(kw in value_lower for kw in self.sensitive_keywords):
                    record[key] = "***REDACTED***"


class QueueLogHandler(logging.Handler):
    """Handler đẩy log vào queue để xử lý bất đồng bộ"""
    
    def __init__(self, queue):
        super().__init__()
        self.queue = queue
    
    def emit(self, record):
        try:
            # Đảm bảo không block nếu queue đầy
            if self.queue.full():
                self.queue.get_nowait()
            self.queue.put_nowait(record)
        except Exception:
            # Fallback cứng ra stderr với bảo vệ tốt hơn
            try:
                sys.stderr.write(f"Log queue overflow: {record.getMessage()[:100]}\n")
            except:
                pass  # Silent fallback nếu stderr cũng fail


def _log_worker_func():
    """Worker xử lý log từ queue bất đồng bộ"""
    while True:
        try:
            record = _log_queue.get(timeout=1.0)
            if record is None:  # Tín hiệu dừng
                break
            
            logger = logging.getLogger(record.name)
            # Xử lý log gốc không qua queue
            if not getattr(record, 'from_worker', False):
                logger.handle(record)
            
            _log_queue.task_done()
        except Empty:
            continue
        except Exception as e:
            sys.stderr.write(f"Log worker error: {str(e)}\n")


def setup_logging(log_dir: str = None, log_level: str = None):
    global _LOGGING_SETUP, _log_worker_thread, _log_listener
    
    if _LOGGING_SETUP:
        return
    
    # Thiết lập giá trị mặc định
    log_dir = log_dir or os.getenv("LOG_DIR", "logs")
    log_level = log_level or os.getenv("LOG_LEVEL", "INFO")
    env = os.getenv("ENVIRONMENT", "dev").lower()
    
    # Tạo thư mục log với fallback (kết hợp ưu điểm đoạn 1)
    log_path = Path(log_dir)
    try:
        log_path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        log_path = Path("/tmp/logs")
        log_path.mkdir(parents=True, exist_ok=True)
    
    # Cấu hình handlers
    handlers = {}
        
    # Console handler (luôn có)
    console_handler = {
        "class": "logging.StreamHandler",
        "level": log_level,
        "stream": sys.stdout,
        "formatter": "standard"
    }
    handlers["console"] = console_handler
    
    # File handlers (không dùng trong test)
    if env != "test":
        # Main log file
        file_handler = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_path / "pipeline.log"),
            "maxBytes": 100 * 1024 * 1024,  # 100MB
            "backupCount": 10,
            "encoding": "utf8",
            "level": "DEBUG",
            "formatter": "json" if env == "production" else "standard"
        }
        handlers["file"] = file_handler
        
        # Error log file
        error_handler = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_path / "errors.log"),
            "maxBytes": 50 * 1024 * 1024,  # 50MB
            "backupCount": 5,
            "encoding": "utf8",
            "level": "ERROR",
            "formatter": "json" if env == "production" else "standard"
        }
        handlers["error_file"] = error_handler
    
    # Formatters
    formatters = {
        "standard": {
            "()": "logging.Formatter",
            "fmt": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "json": {
            "()": f"{__name__}.SafeLogFormatter"
        }
    }
    
    # Cấu hình loggers
    logger_config = {
        "handlers": list(handlers.keys()),
        "level": "DEBUG",  # Cho phép tất cả log, handler sẽ lọc
        "propagate": False
    }
    
    # Cấu hình dictionary
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": handlers,
        "loggers": {
            "": logger_config,  # Root logger
            "sqlalchemy": {"level": "WARNING"},
            "urllib3": {"level": "WARNING"},
            "boto3": {"level": "WARNING"},
            "botocore": {"level": "WARNING"},
            "requests": {"level": "WARNING"}
        }
    }
    
    # Áp dụng cấu hình
    logging.config.dictConfig(config)
    
    # Tích hợp Sentry cho production
    if env == "production" and os.getenv("SENTRY_DSN"):
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration
            
            sentry_logging = LoggingIntegration(
                level=logging.WARNING,
                event_level=logging.ERROR
            )
            
            sentry_sdk.init(
                dsn=os.getenv("SENTRY_DSN"),
                integrations=[sentry_logging],
                traces_sample_rate=0.1,  # Tối ưu performance
                environment=env
            )
            
            # Thêm Sentry handler
            from sentry_sdk.integrations.logging import SentryHandler
            sentry_handler = SentryHandler()
            sentry_handler.setLevel(logging.ERROR)
            logging.getLogger('').addHandler(sentry_handler)
            
        except ImportError:
            logging.getLogger(__name__).warning(
                "Sentry SDK not installed. Skipping Sentry integration."
            )
    
    # Thiết lập hệ thống log bất đồng bộ
    if env != "test":
        # Tạo và khởi động worker thread
        _log_worker_thread = threading.Thread(
            target=_log_worker_func,
            name="LogWorker",
            daemon=True
        )
        _log_worker_thread.start()
        
        # Thay thế tất cả handlers bằng QueueHandler
        root_logger = logging.getLogger()
        queue_handler = QueueLogHandler(_log_queue)
        queue_handler.setLevel(logging.DEBUG)  # Bắt tất cả log
        
        # Giữ lại các handler cũ để xử lý lỗi queue
        original_handlers = root_logger.handlers.copy()
        root_logger.handlers = [queue_handler]
        
        # Lưu listener để dọn dẹp
        _log_listener = {
            "original_handlers": original_handlers,
            "queue_handler": queue_handler
        }
    
    # Ghi nhận khởi động hệ thống log
    logger = logging.getLogger(__name__)
    logger.info(f"Logging system initialized in {env} mode")
    logger.debug(f"Log directory: {os.path.abspath(log_dir)}")
    
    # Đăng ký dọn dẹp khi thoát
    atexit.register(teardown_logging)
    
    _LOGGING_SETUP = True


def teardown_logging():
    """Dọn dẹp tài nguyên logging khi kết thúc ứng dụng"""
    global _log_queue, _log_worker_thread, _log_listener, _LOGGING_SETUP
    
    try:
        # Gửi tín hiệu dừng worker
        if _log_worker_thread and _log_worker_thread.is_alive():
            _log_queue.put(None)
            _log_worker_thread.join(timeout=5.0)
        
        # Xử lý log còn lại trong queue
        while not _log_queue.empty():
            try:
                record = _log_queue.get_nowait()
                if record is None:
                    continue
                    
                # Đánh dấu log từ worker để tránh đệ quy
                setattr(record, 'from_worker', True)
                logger = logging.getLogger(record.name)
                logger.handle(record)
                _log_queue.task_done()
            except Empty:
                break
        
        # Khôi phục handlers gốc để flush log cuối cùng
        if _log_listener:
            root_logger = logging.getLogger()
            queue_handler = _log_listener["queue_handler"]
            
            if queue_handler in root_logger.handlers:
                root_logger.removeHandler(queue_handler)
                
            # Thêm lại handlers gốc và flush
            for handler in _log_listener["original_handlers"]:
                root_logger.addHandler(handler)
            
            # Ghi log shutdown
            logging.info("Flushing final logs before shutdown")
            logging.shutdown()
    
    except Exception as e:
        sys.stderr.write(f"Log teardown error: {str(e)}\n")
    finally:
        _log_worker_thread = None
        _log_listener = None
        _LOGGING_SETUP = False
        atexit.unregister(teardown_logging)