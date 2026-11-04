"""Independent sessions with explicit PostgreSQL connection policy."""

import logging
import os
import threading
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config.settings import get_config

logger = logging.getLogger(__name__)


class DatabaseConnector:
    _engine = None
    _session_factory = None
    _lock = threading.RLock()

    @classmethod
    def get_engine(cls):
        with cls._lock:
            if cls._engine is None:
                url = os.getenv("DATABASE_URL")
                if not url:
                    settings = get_config().db
                    if not settings.is_configured:
                        raise RuntimeError("Configure DATABASE_URL or DB_HOST/DB_NAME/DB_USER/DB_PASSWORD")
                    url = settings.dsn
                if not url.startswith(("postgresql://", "postgresql+psycopg2://")):
                    raise ValueError("This application requires PostgreSQL")
                args = {
                    "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
                    "options": f"-c timezone=UTC -c statement_timeout={int(os.getenv('DB_STATEMENT_TIMEOUT_MS', '120000'))}",
                }
                if os.getenv("DB_SSL_ENABLED", "false").lower() == "true":
                    args["sslmode"] = os.getenv("DB_SSL_MODE", "verify-full")
                    for variable, key in (("DB_SSL_CA", "sslrootcert"), ("DB_SSL_CERT", "sslcert"), ("DB_SSL_KEY", "sslkey")):
                        if os.getenv(variable):
                            args[key] = os.environ[variable]
                cls._engine = create_engine(url, pool_pre_ping=True,
                    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
                    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
                    pool_recycle=1800, connect_args=args)
            return cls._engine

    @classmethod
    def check_connection(cls, max_retries=1):
        try:
            with cls.get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.error("PostgreSQL connection unavailable")
            return False

    @classmethod
    def get_session_factory(cls):
        with cls._lock:
            if cls._session_factory is None:
                cls._session_factory = sessionmaker(bind=cls.get_engine(), autoflush=False, expire_on_commit=False)
            return cls._session_factory

    @classmethod
    def get_session(cls):
        return cls.get_session_factory()()

    @classmethod
    @contextmanager
    def session_scope(cls):
        session = cls.get_session()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    @classmethod
    def execute_sql_file(cls, file_path, max_retries=1):
        try:
            with cls.get_engine().begin() as connection:
                connection.exec_driver_sql(Path(file_path).read_text(encoding="utf-8"), execution_options={"no_parameters": True})
            return True
        except Exception:
            logger.error("SQL file execution failed: %s", Path(file_path).name)
            return False

    @classmethod
    def close_all_connections(cls):
        with cls._lock:
            if cls._engine is not None:
                cls._engine.dispose()
            cls._engine = None
            cls._session_factory = None

    @classmethod
    def get_connection_info(cls):
        engine = cls.get_engine()
        return {"url": engine.url.render_as_string(hide_password=True), "pool_size": engine.pool.size()}
