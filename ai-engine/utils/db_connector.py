# ai-engine\utils\db_connector.py
import logging
import os
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.pool import QueuePool
from config.settings import config
import time
import threading

logger = logging.getLogger(__name__)

class DatabaseConnector:
    _engine = None
    _session_factory = None
    _lock = threading.Lock()
    
    @classmethod
    def get_engine(cls):
        """Tạo engine kết nối an toàn với SSL và connection recycling"""
        with cls._lock:
            if cls._engine is None:
                try:
                    dsn = config.db.dsn
                    
                    # Cấu hình SSL động
                    ssl_args = {}
                    if os.getenv("DB_SSL_ENABLED", "false").lower() == "true":
                        ssl_args = {
                            "sslmode": "verify-full",
                            "sslrootcert": os.getenv("DB_SSL_CA", "/etc/ssl/certs/ca-certificates.crt"),
                            "sslcert": os.getenv("DB_SSL_CERT"),
                            "sslkey": os.getenv("DB_SSL_KEY")
                        }
                    
                    cls._engine = create_engine(
                        dsn,
                        pool_size=10,
                        max_overflow=20,
                        pool_recycle=3600,
                        pool_pre_ping=True,
                        pool_use_lifo=True,
                        poolclass=QueuePool,
                        connect_args={
                            **ssl_args,
                            "options": "-c statement_timeout=30000"
                        }
                    )
                    
                    # Thiết lập UTC
                    with cls._engine.connect() as conn:
                        conn.execute(text("SET TIME ZONE 'UTC';"))
                    
                    logger.info("Database engine initialized")
                except OperationalError as e:
                    logger.critical(f"Database connection failed: {str(e)}")
                    # Fallback cho local
                    if "localhost" in dsn or "127.0.0.1" in dsn:
                        logger.warning("Trying without SSL for local connection")
                        cls._engine = create_engine(dsn)
                    else:
                        raise
        return cls._engine

    @classmethod
    def check_connection(cls, max_retries: int = 3) -> bool:
        """Kiểm tra kết nối database với retry"""
        for i in range(max_retries):
            try:
                with cls.get_engine().connect() as conn:
                    conn.execute(text("SELECT 1"))
                return True
            except OperationalError:
                logger.warning(f"Connection failed (attempt {i+1}/{max_retries})")
                time.sleep(2 ** i)
        return False

    @classmethod
    def get_session(cls):
        """Tạo scoped session factory"""
        with cls._lock:
            if cls._session_factory is None:
                cls._session_factory = sessionmaker(
                    bind=cls.get_engine(),
                    autocommit=False,
                    autoflush=False,
                    expire_on_commit=False
                )
        return scoped_session(cls._session_factory)

    @classmethod
    @contextmanager
    def session_scope(cls):
        """Context manager cho session tự động commit/rollback/close"""
        session = cls.get_session()()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database operation failed: {str(e)}")
            raise
        finally:
            try:
                session.close()
            finally:
                # Luôn gọi remove() để giải phóng session
                cls.get_session().remove()

    @classmethod
    def execute_sql_file(cls, file_path: str, max_retries: int = 3):
        """Thực thi file SQL với retry logic"""
        for attempt in range(max_retries):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    sql_content = f.read()
                
                with cls.get_engine().begin() as conn:
                    conn.execute(text(sql_content))
                
                logger.info(f"Executed SQL file: {file_path}")
                return True
            except OperationalError as e:
                logger.warning(f"Database error (attempt {attempt+1}/{max_retries}): {str(e)}")
                time.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Error executing SQL file {file_path}: {str(e)}")
                return False
        logger.error(f"Failed after {max_retries} attempts")
        return False

# Health check khi import
if not DatabaseConnector.check_connection():
    logger.critical("Critical: Database connection test failed on startup")