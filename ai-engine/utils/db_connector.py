# ai-engine\utils\db_connector.py
import logging
import os
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.pool import QueuePool
from config.settings import get_config
from sqlalchemy import create_engine, text
import time
import threading
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class DatabaseConnector:
    _engine = None
    _session_factory = None
    _lock = threading.RLock()  # Use RLock to prevent deadlocks
    _config = None
    
    @classmethod
    def _get_config(cls):
        """Get config instance safely"""
        if cls._config is None:
            cls._config = get_config()
        return cls._config
    
    @classmethod
    def get_engine(cls):
        """Tạo engine kết nối an toàn với SSL và connection recycling"""
        with cls._lock:
            if cls._engine is None:
                config = cls._get_config()
                
                # Check if database is configured
                if not config.db.is_configured:
                    if config.is_development:
                        logger.warning("Database not configured - this may be intentional in dev environment")
                        return None
                    else:
                        raise RuntimeError("Database configuration is required in production")
                
                try:
                    dsn = config.db.dsn
                    
                    # Cấu hình SSL động
                    ssl_args = cls._get_ssl_config()
                    
                    # Enhanced connection args
                    connect_args = {
                        **ssl_args,
                        "options": "-c statement_timeout=30000 -c timezone=UTC"
                    }
                    
                    cls._engine = create_engine(
                        dsn,
                        pool_size=10,
                        max_overflow=20,
                        pool_recycle=3600,  # Recycle connections after 1 hour
                        pool_pre_ping=True,  # Verify connections before use
                        pool_use_lifo=True,  # Use LIFO for better connection reuse
                        poolclass=QueuePool,
                        connect_args=connect_args,
                        echo=config.is_development,  # Log SQL in development
                        echo_pool=config.is_development,  # Log pool events in development
                        future=True  # Use SQLAlchemy 2.0 style
                    )
                    
                    # Test connection and set timezone
                    cls._initialize_connection()
                    
                    logger.info("Database engine initialized successfully")
                    
                except OperationalError as e:
                    logger.error(f"Database connection failed: {str(e)}")
                    # Fallback cho local development
                    if cls._is_local_connection(dsn):
                        logger.warning("Trying simplified connection for local development")
                        cls._engine = cls._create_fallback_engine(dsn)
                    else:
                        raise RuntimeError(f"Database connection failed: {str(e)}") from e
                except Exception as e:
                    logger.critical(f"Unexpected error creating database engine: {str(e)}")
                    raise RuntimeError(f"Database engine creation failed: {str(e)}") from e
                    
        return cls._engine
    
    @classmethod
    def _get_ssl_config(cls) -> Dict[str, Any]:
        """Get SSL configuration"""
        ssl_args = {}
        if os.getenv("DB_SSL_ENABLED", "false").lower() == "true":
            ssl_args = {
                "sslmode": os.getenv("DB_SSL_MODE", "require"),
                "sslrootcert": os.getenv("DB_SSL_CA", "/etc/ssl/certs/ca-certificates.crt"),
            }
            
            # Optional client certificates
            ssl_cert = os.getenv("DB_SSL_CERT")
            ssl_key = os.getenv("DB_SSL_KEY")
            if ssl_cert and ssl_key:
                ssl_args.update({
                    "sslcert": ssl_cert,
                    "sslkey": ssl_key
                })
        return ssl_args
    
    @classmethod
    def _is_local_connection(cls, dsn: str) -> bool:
        """Check if connection is local"""
        return any(host in dsn.lower() for host in ["localhost", "127.0.0.1", "::1"])
    
    @classmethod
    def _create_fallback_engine(cls, dsn: str):
        """Create fallback engine for local development"""
        return create_engine(
            dsn,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
            pool_pre_ping=True,
            future=True
        )
    
    @classmethod
    def _initialize_connection(cls):
        """Initialize connection settings"""
        try:
            with cls._engine.connect() as conn:
                # Set timezone to UTC
                conn.execute(text("SET TIME ZONE 'UTC'"))
                # Test query
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                logger.info(f"Connected to PostgreSQL: {version}")
        except Exception as e:
            logger.error(f"Failed to initialize connection: {str(e)}")
            raise

    @classmethod
    def check_connection(cls, max_retries: int = 3) -> bool:
        """Kiểm tra kết nối database với retry"""
        engine = cls.get_engine()
        if engine is None:
            logger.warning("No database engine available")
            return False
            
        for attempt in range(max_retries):
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.debug(f"Database connection check passed (attempt {attempt + 1})")
                return True
            except OperationalError as e:
                wait_time = 2 ** attempt
                logger.warning(f"Connection check failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
            except Exception as e:
                logger.error(f"Unexpected error during connection check: {str(e)}")
                break
                
        logger.error("Database connection check failed after all retries")
        return False

    @classmethod
    def get_session_factory(cls):
        """Get session factory (lazy initialization)"""
        with cls._lock:
            if cls._session_factory is None:
                engine = cls.get_engine()
                if engine is None:
                    raise RuntimeError("Cannot create session factory without database engine")
                    
                cls._session_factory = sessionmaker(
                    bind=engine,
                    autocommit=False,
                    autoflush=False,
                    expire_on_commit=False,
                    future=True  # SQLAlchemy 2.0 style
                )
        return cls._session_factory

    @classmethod
    def get_session(cls):
        """Tạo scoped session"""
        session_factory = cls.get_session_factory()
        return scoped_session(session_factory)

    @classmethod
    @contextmanager
    def session_scope(cls):
        """Context manager cho session tự động commit/rollback/close"""
        session_maker = cls.get_session()
        session = session_maker()
        try:
            yield session
            session.commit()
            logger.debug("Database session committed successfully")
        except Exception as e:
            session.rollback()
            logger.error(f"Database operation failed, rolled back: {str(e)}")
            raise
        finally:
            try:
                session.close()
            except Exception as e:
                logger.warning(f"Error closing session: {str(e)}")
            finally:
                # Always remove scoped session
                try:
                    session_maker.remove()
                except Exception as e:
                    logger.warning(f"Error removing scoped session: {str(e)}")

    @classmethod
    def execute_sql_file(cls, file_path: str, max_retries: int = 3) -> bool:
        """Thực thi file SQL với retry logic"""
        if not os.path.exists(file_path):
            logger.error(f"SQL file not found: {file_path}")
            return False
            
        engine = cls.get_engine()
        if engine is None:
            logger.error("No database engine available for SQL execution")
            return False
        
        for attempt in range(max_retries):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    sql_content = f.read().strip()
                
                if not sql_content:
                    logger.warning(f"SQL file is empty: {file_path}")
                    return True
                
                with engine.begin() as conn:
                    # Execute SQL content
                    conn.execute(text(sql_content))
                
                logger.info(f"Successfully executed SQL file: {file_path}")
                return True
                
            except OperationalError as e:
                wait_time = 2 ** attempt
                logger.warning(f"Database error executing SQL file (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
            except FileNotFoundError:
                logger.error(f"SQL file not found: {file_path}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error executing SQL file {file_path}: {str(e)}")
                return False
                
        logger.error(f"Failed to execute SQL file after {max_retries} attempts: {file_path}")
        return False

    @classmethod
    def close_all_connections(cls):
        """Close all database connections - useful for cleanup"""
        with cls._lock:
            try:
                if cls._session_factory:
                    # Remove all scoped sessions
                    scoped_session(cls._session_factory).remove()
                    
                if cls._engine:
                    cls._engine.dispose()
                    logger.info("Database connections closed")
                    
            except Exception as e:
                logger.warning(f"Error closing database connections: {str(e)}")
            finally:
                cls._engine = None
                cls._session_factory = None

    @classmethod
    def get_connection_info(cls) -> Optional[Dict[str, Any]]:
        """Get database connection information for debugging"""
        engine = cls.get_engine()
        if engine is None:
            return None
            
        try:
            pool = engine.pool
            return {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "url": str(engine.url).replace(engine.url.password or "", "***")
            }
        except Exception as e:
            logger.error(f"Error getting connection info: {str(e)}")
            return None

# # Conditional health check - only in production or when explicitly requested
# def _should_run_health_check() -> bool:
#     """Determine if health check should run on import"""
#     config = get_config()
#     # Only run health check in production or when explicitly enabled
#     return (
#         config.is_production or 
#         os.getenv("DB_HEALTH_CHECK_ON_IMPORT", "false").lower() == "true"
#     )

# # Health check khi import (conditional)
# if _should_run_health_check():
#     try:
#         if not DatabaseConnector.check_connection():
#             logger.critical("CRITICAL: Database connection test failed on startup")
#         else:
#             logger.info("Database connection test passed on startup")
#     except Exception as e:
#         logger.critical(f"CRITICAL: Database health check failed on startup: {str(e)}")
# else:
#     logger.debug("Skipping database health check on import (development mode)")