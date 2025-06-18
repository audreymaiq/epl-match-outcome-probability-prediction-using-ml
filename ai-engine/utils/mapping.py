# utils/mapping.py

from typing import Optional
from sqlalchemy import text
from utils.database import get_engine


def get_internal_id(external_id: str, entity_type: str, source_system: str) -> Optional[int]:
    """
    Truy vấn để lấy internal_id tương ứng từ external_id + entity_type + source_system.
    """
    query = """
        SELECT internal_id
        FROM "ExternalMapping"
        WHERE external_id = :external_id
            AND entity_type = :entity_type
            AND source_system = :source_system
        LIMIT 1
    """
    with get_engine().connect() as conn:
        result = conn.execute(
            text(query),
            {
                "external_id": external_id,
                "entity_type": entity_type,
                "source_system": source_system
            }
        ).fetchone()
        return result[0] if result else None


def insert_mapping(
    external_id: str,
    internal_id: int,
    entity_type: str,
    source_system: str,
    source_detail: Optional[str] = None
):
    """
    Thêm ánh xạ mới giữa external_id và internal_id.
    Nếu ánh xạ đã tồn tại, sẽ bỏ qua (idempotent).
    """
    query = """
        INSERT INTO "ExternalMapping" (
            external_id, internal_id, entity_type,
            source_system, source_detail, created_at, updated_at
        )
        VALUES (
            :external_id, :internal_id, :entity_type,
            :source_system, :source_detail, now(), now()
        )
        ON CONFLICT (external_id, entity_type, source_system)
        DO NOTHING
    """
    with get_engine().connect() as conn:
        conn.execute(
            text(query),
            {
                "external_id": external_id,
                "internal_id": internal_id,
                "entity_type": entity_type,
                "source_system": source_system,
                "source_detail": source_detail
            }
        )
        conn.commit()


def upsert_mapping(
    external_id: str,
    internal_id: int,
    entity_type: str,
    source_system: str,
    source_detail: Optional[str] = None
):
    """
    Thêm mới hoặc cập nhật ánh xạ nếu đã tồn tại (cập nhật internal_id, source_detail, updated_at).
    """
    query = """
        INSERT INTO "ExternalMapping" (
            external_id, internal_id, entity_type,
            source_system, source_detail, created_at, updated_at
        )
        VALUES (
            :external_id, :internal_id, :entity_type,
            :source_system, :source_detail, now(), now()
        )
        ON CONFLICT (external_id, entity_type, source_system)
        DO UPDATE SET
            internal_id = EXCLUDED.internal_id,
            source_detail = EXCLUDED.source_detail,
            updated_at = now()
    """
    with get_engine().connect() as conn:
        conn.execute(
            text(query),
            {
                "external_id": external_id,
                "internal_id": internal_id,
                "entity_type": entity_type,
                "source_system": source_system,
                "source_detail": source_detail
            }
        )
        conn.commit()
