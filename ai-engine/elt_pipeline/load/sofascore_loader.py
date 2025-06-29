# elt_pipeline\load\sofascore_loader.py

"""
SofaScore ETL Pipeline: Parser: Chỉ phân tích và chuẩn hóa dữ liệu thô thành các đối tượng có cấu trúc.

"""

import logging
from typing import Optional
from sqlalchemy.orm import Session

from utils.db_connector import DatabaseConnector
from utils.external_mapping import get_internal_id, upsert_mapping
from elt_pipeline.transform.sofascore_transformer import (
    ParsedTeam, ParsedStadium, ParsedReferee, ParsedMatch
)

logger = logging.getLogger(__name__)

# --- LỚP LOADER: CHỈ GHI VÀO DATABASE ---
class SofaScoreLoader:
    """Chịu trách nhiệm ghi các đối tượng đã chuẩn hóa vào DB."""

    def __init__(self, session: Session):
        self.session = session
    
    def _upsert_and_map(self, entity_type: str, external_id: int, name: str, table: str) -> Optional[int]:
        """Hàm chung để upsert Team/Referee/Player và tạo mapping."""
        # Kiểm tra mapping trước
        internal_id = get_internal_id(str(external_id), entity_type, "sofascore", session=self.session)
        if internal_id:
            return internal_id

        # Nếu không có, upsert và tạo mapping
        query = f"""
            INSERT INTO "{table}" (name) VALUES (:name)
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id;
        """
        result = self.session.execute(query, {"name": name}).scalar_one_or_none()
        
        if result:
            internal_id = result
            upsert_mapping(str(external_id), internal_id, entity_type, "sofascore", session=self.session)
            return internal_id
        return None

    def upsert_team(self, team: ParsedTeam) -> Optional[int]:
        if team.internal_id:
            return team.internal_id
        
        team.internal_id = self._upsert_and_map("team", team.external_id, team.name, "Teams")
        return team.internal_id

    def upsert_stadium(self, stadium: ParsedStadium) -> Optional[int]:
        if stadium.internal_id:
            return stadium.internal_id
        
        query = """
            INSERT INTO "Stadiums" (name, city, capacity) VALUES (:name, :city, :capacity)
            ON CONFLICT (name) DO UPDATE SET
                city = EXCLUDED.city,
                capacity = EXCLUDED.capacity
            RETURNING id;
        """
        result = self.session.execute(query, {
            "name": stadium.name,
            "city": stadium.city,
            "capacity": stadium.capacity
        }).scalar_one_or_none()
        stadium.internal_id = result
        return stadium.internal_id

    def upsert_referee(self, referee: ParsedReferee) -> Optional[int]:
        if referee.internal_id:
            return referee.internal_id

        referee.internal_id = self._upsert_and_map("referee", referee.external_id, referee.name, "Referees")
        return referee.internal_id
        
    def upsert_match(self, match: ParsedMatch) -> Optional[int]:
        # Đảm bảo các thực thể liên quan đã có internal_id
        if not match.home_team.internal_id or not match.away_team.internal_id:
            logger.error("Cannot insert match without internal team IDs", extra={"match_ext_id": match.external_id})
            return None

        # Kiểm tra mapping trước
        internal_id = get_internal_id(str(match.external_id), "match", "sofascore", session=self.session)
        if internal_id:
            # Nếu đã có, có thể cập nhật
            logger.debug("Match already exists, skipping insert.", extra={"ext_id": match.external_id})
            return internal_id
            
        query = """
            INSERT INTO "Matches" (
                match_datetime, home_team_id, away_team_id, home_goals, away_goals,
                half_time_home_goals, half_time_away_goals, status, round,
                stadium_id, referee_id
            )
            VALUES (
                :dt, :h_id, :a_id, :hg, :ag, :hthg, :htag, :status, :round, :st_id, :ref_id
            )
            ON CONFLICT DO NOTHING
            RETURNING id;
        """
        
        params = {
            "dt": match.match_datetime,
            "h_id": match.home_team.internal_id,
            "a_id": match.away_team.internal_id,
            "hg": match.home_goals,
            "ag": match.away_goals,
            "hthg": match.ht_home_goals,
            "htag": match.ht_away_goals,
            "status": match.status,
            "round": match.round,
            "st_id": match.stadium.internal_id if match.stadium else None,
            "ref_id": match.referee.internal_id if match.referee else None,
        }
        
        result = self.session.execute(query, params).scalar_one_or_none()
        
        if result:
            match.internal_id = result
            upsert_mapping(str(match.external_id), match.internal_id, "match", "sofascore", session=self.session)
            return match.internal_id
        return None