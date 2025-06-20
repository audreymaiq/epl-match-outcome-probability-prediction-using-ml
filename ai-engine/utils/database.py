# utils/database.py
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from config.config import DB_CONFIG
import logging

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None

def get_engine():
    global _engine
    if _engine is None:
        conn_str = (
            f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
        )
        _engine = create_engine(conn_str, pool_size=10, max_overflow=20)
        
        # Đặt timezone UTC cho tất cả kết nối
        with _engine.connect() as conn:
            conn.execute(text("SET TIME ZONE 'UTC';"))
            conn.commit()
            
    return _engine

def get_session():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return scoped_session(_session_factory)

def execute_sql_file(file_path: str):
    """Thực thi một file SQL"""
    try:
        with open(file_path, 'r') as f:
            sql_content = f.read()
        
        with get_engine().begin() as conn:
            conn.execute(text(sql_content))
        
        logger.info(f"Executed SQL file: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error executing SQL file {file_path}: {str(e)}")
        return False
