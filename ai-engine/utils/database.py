# utils/database.py
from sqlalchemy import create_engine, text
from config.config import DB_CONFIG

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        conn_str = (
            f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
        )
        _engine = create_engine(conn_str)
    return _engine

def execute_query(query, params=None):
    with get_engine().connect() as conn:
        result = conn.execute(text(query), params or {})
        conn.commit()  # Chỉ cần nếu query là INSERT/UPDATE/DELETE
        return result
