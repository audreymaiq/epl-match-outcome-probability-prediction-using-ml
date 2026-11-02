# backend\utils\logging_config.py

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
import threading

# Global setup flag
_LOGGING_SETUP = False # Cờ để đảm bảo setup chỉ chạy một lần duy nhất
_log_queue = Queue(maxsize=1000) # Hàng đợi chứa các log record để xử lý bất đồng bộ
_log_worker_thread = None # Thread xử lý log từ queue
_log_listener = None # Lưu lại thông tin các handler gốc để teardown


class SafeLogFormatter(jsonlogger.JsonFormatter):
    """
    Formatter tùy chỉnh để tạo log dạng JSON, đồng thời tự động che (redact) các thông tin nhạy cảm.
    Kế thừa từ `jsonlogger.JsonFormatter` để có sẵn chức năng định dạng JSON.
    Mục đích: Đảm bảo log không vô tình làm lộ các thông tin như mật khẩu, API key.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Định nghĩa danh sách các từ khóa nhạy cảm. Bất kỳ trường log nào (key hoặc value) chứa các từ khóa này sẽ bị che đi.        
        self.sensitive_keywords = [
            "password", "api_key", "secret", "token", 
            "access_token", "auth_key", "credential"
        ]
    
    def add_fields(self, log_record, record, message_dict):
        """
        Ghi đè phương thức này để thêm các trường tùy chỉnh vào mỗi bản ghi log JSON.
        Phương thức này được `jsonlogger` tự động gọi cho mỗi log.
        - log_record: là dictionary cuối cùng sẽ được chuyển thành JSON.
        - record: là đối tượng LogRecord gốc của thư viện logging.
        - message_dict: là dictionary được phân tích từ thông điệp log.
        """

        super().add_fields(log_record, record, message_dict)
        
        # Thống nhất biến môi trường
        log_record["service"] = "premier-league-pipeline"
        log_record["environment"] = os.getenv("ENVIRONMENT", "unknown")
        log_record["host"] = os.getenv("HOSTNAME", "unknown")
        
        # Timestamp UTC chính xác
        log_record["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Redact toàn bộ record
        self.redact_sensitive_data(log_record)
    
    def redact_sensitive_data(self, record):
        """
        Quét và che thông tin nhạy cảm trong mọi trường của một bản ghi log.
        Hàm này lặp qua tất cả các key-value trong dictionary của log.
        """
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
    """
    Thay vì ghi log ra file hay console, nó sẽ đẩy
    bản ghi log vào một đối tượng Queue.
    Mục đích: Tách rời việc tạo log (nhanh) và việc xử lý log (chậm, do I/O).
    Điều này giúp ứng dụng chính không bị block (chờ) khi ghi log.
    """
    
    def __init__(self, queue):
        super().__init__()
        self.queue = queue
    
    def emit(self, record):
        try:
            # Đảm bảo không block nếu queue đầy
            if self.queue.full():
                sys.stderr.write("Log queue is full, subsequent logs may be dropped.\n")
                return 
            self.queue.put_nowait(record)
        except Exception:
            # Fallback cứng ra stderr với bảo vệ tốt hơn
            try:
                sys.stderr.write(f"Log queue overflow: {record.getMessage()[:100]}\n")
            except:
                pass  # Silent fallback nếu stderr cũng fail


def _log_worker_func(original_handlers): 
    """
    Hàm mục tiêu (target function) cho luồng worker.
    Chạy trong một vòng lặp vô hạn, liên tục lấy log từ `_log_queue` và xử lý chúng.
    - `original_handlers`: là danh sách các handler thực sự (ghi file, console) được truyền vào.
    """
    while True:
        try:
            record = _log_queue.get(timeout=1.0)
            if record is None:  # Tín hiệu dừng
                break
            
            for handler in original_handlers:
                if record.levelno >= handler.level:
                    handler.emit(record)
            
            _log_queue.task_done()
        except Empty:
            continue
        except Exception as e:
            sys.stderr.write(f"Log worker error: {str(e)}\n")

_setup_lock = threading.Lock()

def setup_logging(log_dir: str = None, log_level: str = None):
    """
    Hàm chính để thiết lập toàn bộ hệ thống logging cho ứng dụng.
    Hàm này chỉ nên được gọi một lần khi ứng dụng khởi động.
    
    - log_dir: Thư mục để lưu file log.
    - log_level: Cấp độ log tối thiểu cho console (VD: "INFO", "DEBUG").
    """
    global _LOGGING_SETUP, _log_worker_thread, _log_listener
    
    if _LOGGING_SETUP:
        return
    
    with _setup_lock:
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
        # Không dùng trong môi trường 'test' để đơn giản hóa việc kiểm thử.
        if env != "test":
            root_logger = logging.getLogger()
            
            # 1. Lưu lại các handler gốc (console, file, error) đang có.
            original_handlers = root_logger.handlers[:]

            # 2. Tạo và khởi động luồng worker.
            # Truyền `original_handlers` vào để worker biết phải dùng handler nào để xử lý log.
            _log_worker_thread = threading.Thread(
                target=_log_worker_func,
                args=(original_handlers,), # <<== TRUYỀN HANDLERS VÀO
                name="LogWorker",
                daemon=True
            )
            _log_worker_thread.start()
            
            # 3. Tạo QueueHandler để đẩy log vào `_log_queue`.
            queue_handler = QueueLogHandler(_log_queue)
            queue_handler.setLevel(logging.DEBUG)  # Bắt tất cả log
            root_logger.handlers = [queue_handler]
            
            # 5. Lưu lại thông tin để có thể dọn dẹp sau này (teardown).
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
    """
    Dọn dẹp tài nguyên logging khi ứng dụng kết thúc.
    Hàm này được `atexit` gọi tự động.
    Mục đích chính: Đảm bảo tất cả các log trong queue đều được xử lý và ghi ra file/console
    trước khi chương trình thoát hoàn toàn, tránh mất log.
    """
    global _log_queue, _log_worker_thread, _log_listener, _LOGGING_SETUP
    if not _LOGGING_SETUP:
        return

    try:
        logging.info("Initiating logging teardown...") # Log sự kiện teardown

        # 1. Gửi tín hiệu dừng và chờ worker thread kết thúc
        if _log_worker_thread and _log_worker_thread.is_alive():
            _log_queue.put(None)
            _log_worker_thread.join(timeout=2.0) # Cho worker thời gian xử lý

        # 2. Khôi phục lại các handler gốc
        root_logger = logging.getLogger()
        if _log_listener:
            queue_handler = _log_listener["queue_handler"]
            if queue_handler in root_logger.handlers:
                root_logger.removeHandler(queue_handler)
            
            # Thêm lại các handler gốc
            for handler in _log_listener["original_handlers"]:
                if handler not in root_logger.handlers:
                    root_logger.addHandler(handler)

        # 3. Bây giờ, xử lý các mục còn lại trong queue bằng các handler gốc
        while not _log_queue.empty():
            try:
                record = _log_queue.get_nowait()
                if record:
                    logger = logging.getLogger(record.name)
                    logger.handle(record) # Sẽ được xử lý bởi file/console handlers
            except Empty:
                break

        logging.info("Final logs flushed. Shutting down logging system.")
        logging.shutdown()

    except Exception as e:
        # Nếu có lỗi trong quá trình dọn dẹp, ghi ra stderr
        sys.stderr.write(f"Error during logging teardown: {str(e)}\n")
    finally:
        # Dù thành công hay thất bại, reset lại các biến toàn cục.
        _log_worker_thread = None
        _log_listener = None
        _LOGGING_SETUP = False