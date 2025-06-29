# elt_pipeline\transform\sofascore_transformer.py

"""
SofaScore ETL Pipeline: Writer: Chỉ ghi các đối tượng đã chuẩn hóa vào database.

"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, Any, Optional

from utils.db_connector import DatabaseConnector
from utils.external_mapping import get_internal_id, upsert_mapping
from utils.logging_config import setup_logging
from config.core_constants import MatchStatus, PlayerPosition, MatchOutcome
from config.field_mappings import (
    unified_status_mapper, unified_position_mapper, unified_outcome_mapper,
    convert_datetime, convert_possession_percent
)
from config.business_constants import BusinessRules, MatchBusinessLogic

# --- Cấu hình ban đầu ---
setup_logging()

# --- ĐỊNH NGHĨA CẤU TRÚC DỮ LIỆU CHUẨN HÓA (Dataclasses) ---

@dataclass
class ParsedTeam:
    external_id: int
    name: str
    internal_id: Optional[int] = None

@dataclass
class ParsedStadium:
    name: str
    city: Optional[str]
    capacity: Optional[int]
    internal_id: Optional[int] = None

@dataclass
class ParsedReferee:
    external_id: int
    name: str
    internal_id: Optional[int] = None

@dataclass
class ParsedMatch:
    external_id: int
    home_team: ParsedTeam
    away_team: ParsedTeam
    match_datetime: datetime
    status: str  
    home_goals: Optional[int]
    away_goals: Optional[int]
    ht_home_goals: Optional[int]
    ht_away_goals: Optional[int]
    stadium: Optional[ParsedStadium]
    referee: Optional[ParsedReferee]
    internal_id: Optional[int] = None
    round: Optional[int] = None


# --- LỚP PARSER: CHỈ PHÂN TÍCH VÀ CHUẨN HÓA DỮ LIỆU ---
class SofaScoreTransformer:
    """Chịu trách nhiệm chuyển đổi JSON thô thành các object dataclass đã chuẩn hóa."""

    def _parse_team(self, raw_team: Dict) -> Optional[ParsedTeam]:
        if not raw_team or not raw_team.get("id") or not raw_team.get("name"):
            return None
        # Chuẩn hóa tên đội bóng ngay tại nguồn
        normalized_name = MatchBusinessLogic.normalize_team_name(raw_team["name"])
        return ParsedTeam(external_id=raw_team["id"], name=normalized_name)

    def _parse_stadium(self, raw_venue: Dict) -> Optional[ParsedStadium]:
        if not raw_venue or not raw_venue.get("stadium"):
            return None
        stadium_data = raw_venue["stadium"]
        city_data = raw_venue.get("city", {})
        return ParsedStadium(
            name=stadium_data["name"],
            city=city_data.get("name"),
            capacity=stadium_data.get("capacity")
        )

    def _parse_referee(self, raw_referee: Dict) -> Optional[ParsedReferee]:
        if not raw_referee or not raw_referee.get("id") or not raw_referee.get("name"):
            return None
        return ParsedReferee(external_id=raw_referee["id"], name=raw_referee["name"])

    def parse_match_list_item(self, raw_match: Dict) -> Optional[ParsedMatch]:
        """Phân tích một item từ danh sách các trận đấu (dữ liệu tóm tắt)."""
        if not raw_match or not raw_match.get("id"):
            return None
        
        home_team = self._parse_team(raw_match.get("homeTeam", {}))
        away_team = self._parse_team(raw_match.get("awayTeam", {}))
        
        if not home_team or not away_team:
            return None
            
        # CHUẨN HÓA DỮ LIỆU ở đây
        status = unified_status_mapper(
            raw_match.get("status", {}).get("description"), api_type='sofascore'
        )
        match_dt = convert_datetime(raw_match.get("startTimestamp"))
        
        if not match_dt:
            return None

        return ParsedMatch(
            external_id=raw_match["id"],
            home_team=home_team,
            away_team=away_team,
            match_datetime=match_dt,
            status=status,
            home_goals=raw_match.get("homeScore", {}).get("current"),
            away_goals=raw_match.get("awayScore", {}).get("current"),
            ht_home_goals=raw_match.get("homeScore", {}).get("period1"),
            ht_away_goals=raw_match.get("awayScore", {}).get("period1"),
            stadium=None,  # Dữ liệu tóm tắt không có
            referee=None,  # Dữ liệu tóm tắt không có
            round=raw_match.get("roundInfo", {}).get("round")
        )

    def enrich_match_with_details(self, match: ParsedMatch, raw_detail: Dict) -> ParsedMatch:
        """Bổ sung thông tin chi tiết vào đối tượng ParsedMatch đã có."""
        stadium = self._parse_stadium(raw_detail.get("venue", {}))
        referee = self._parse_referee(raw_detail.get("referee", {}))
        
        if stadium:
            match.stadium = stadium
        if referee:
            match.referee = referee
            
        return match

    def transform_match_data(self, raw_summary: Dict, raw_detail: Dict) -> Optional[ParsedMatch]:
        """
        Combine summary and detail data into a complete ParsedMatch object.
        
        Args:
            raw_summary: Match summary data from list endpoint
            raw_detail: Detailed match data from detail endpoint
            
        Returns:
            Complete ParsedMatch object with all available data
        """
        # Parse the basic match data from summary
        match = self.parse_match_list_item(raw_summary)
        
        if not match:
            return None
            
        # Enrich with detailed data if available
        if raw_detail:
            match = self.enrich_match_with_details(match, raw_detail)
            
        return match