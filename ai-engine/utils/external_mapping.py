# ai-engine\utils\external_mapping.py

from typing import Optional
from sqlalchemy import text, exc
from sqlalchemy.orm import Session
from utils.db_connector import DatabaseConnector  
from config.business_constants import VALID_ENTITY_TYPES  
import logging

logger = logging.getLogger(__name__)

def get_internal_id(
    external_id: str, 
    entity_type: str, 
    source_system: str,
    session: Optional[Session] = None
) -> Optional[int]:
    """
    Truy vấn internal_id từ mapping table với validation
    
    Args:
        entity_type: Phải nằm trong VALID_ENTITY_TYPES
        source_system: Tên hệ thống nguồn (max 50 ký tự)
    
    Returns:
        internal_id hoặc None nếu không tìm thấy
    """
    # Validate entity_type
    if entity_type not in VALID_ENTITY_TYPES:
        raise ValueError(f"Invalid entity_type: {entity_type}. Valid types: {VALID_ENTITY_TYPES}")
    
    query = text("""
        SELECT internal_id
        FROM "ExternalMapping"
        WHERE external_id = :external_id
            AND entity_type = :entity_type
            AND source_system = :source_system
        LIMIT 1
    """)
    
    params = {
        "external_id": external_id,
        "entity_type": entity_type,
        "source_system": source_system[:50]  # Ensure max length
    }
    
    try:
        # Sử dụng session context manager mới
        if session is None:
            with DatabaseConnector.session_scope() as session:
                return _execute_query(session, query, params)
        else:
            return _execute_query(session, query, params)
            
    except exc.SQLAlchemyError as e:
        logger.error(f"Database error in get_internal_id: {str(e)}")
        return None

def _execute_query(session: Session, query, params) -> Optional[int]:
    """Thực thi truy vấn và trả về kết quả"""
    result = session.execute(query, params).scalar_one_or_none()
    return result

def upsert_mapping(
    external_id: str,
    internal_id: int,
    entity_type: str,
    source_system: str,
    source_detail: Optional[str] = None,
    session: Optional[Session] = None
):
    """
    UPSERT mapping với transaction management và validation
    
    Throws:
        ValueError: Nếu entity_type không hợp lệ
        SQLAlchemyError: Cho lỗi database
    """
    # Validate entity_type
    if entity_type not in VALID_ENTITY_TYPES:
        raise ValueError(f"Invalid entity_type: {entity_type}. Valid types: {VALID_ENTITY_TYPES}")
    
    query = text("""
        INSERT INTO "ExternalMapping" (
            external_id, internal_id, entity_type,
            source_system, source_detail
        )
        VALUES (
            :external_id, :internal_id, :entity_type,
            :source_system, :source_detail
        )
        ON CONFLICT (external_id, entity_type, source_system)
        DO UPDATE SET
            internal_id = EXCLUDED.internal_id,
            source_detail = EXCLUDED.source_detail,
            updated_at = NOW()
        RETURNING id
    """)
    
    params = {
        "external_id": external_id,
        "internal_id": internal_id,
        "entity_type": entity_type,
        "source_system": source_system[:50],  # Trim to max length
        "source_detail": source_detail
    }
    
    try:
        if session is None:
            with DatabaseConnector.session_scope() as session:
                result = session.execute(query, params)
                session.flush()
                logger.info(f"Upserted mapping: {result.scalar()}")
        else:
            result = session.execute(query, params)
            logger.debug(f"Upserted mapping in external session: {result.scalar()}")
            
    except exc.IntegrityError as e:
        logger.error(f"Integrity error in upsert_mapping: {str(e)}")
        raise ValueError("Invalid internal_id or constraint violation") from e
        
    except exc.SQLAlchemyError as e:
        logger.error(f"Database error in upsert_mapping: {str(e)}")
        raise