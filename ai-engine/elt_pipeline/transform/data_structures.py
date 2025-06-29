# elt_pipeline/transform/data_structures.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

"""
Định nghĩa các cấu trúc dữ liệu (schemas) đã được chuẩn hóa.
Đây là output của Transformer và là input của Loader.
"""

@dataclass
class ParsedTeam:
    """Dữ liệu chuẩn hóa cho một đội bóng."""
    external_id: int
    name: str
    internal_id: Optional[int] = None  # Sẽ được Loader điền vào

@dataclass
class ParsedStadium:
    """Dữ liệu chuẩn hóa cho một sân vận động."""
    name: str
    city: Optional[str]
    capacity: Optional[int]
    internal_id: Optional[int] = None  

@dataclass
class ParsedReferee:
    """Dữ liệu chuẩn hóa cho một trọng tài."""
    external_id: int
    name: str
    internal_id: Optional[int] = None  

@dataclass
class ParsedLeague:
    name: str
    country: str
    internal_id: Optional[int] = None

@dataclass
class ParsedSeason:
    name: str        
    start_year: int
    end_year: int
    league: ParsedLeague
    internal_id: Optional[int] = None

@dataclass
class ParsedMatch:
    """
    Dữ liệu chuẩn hóa hoàn chỉnh cho một trận đấu.
    Bao gồm cả các thông tin nghiệp vụ đã được làm giàu.
    """
    # ID & Metadata
    external_id: int
    season: ParsedSeason
    match_datetime: datetime
    round: Optional[int]
    
    # Teams
    home_team: ParsedTeam
    away_team: ParsedTeam
    
    # Status & Outcome
    status: str             # Trạng thái chuẩn hóa (e.g., FINISHED)
    outcome: str            # Kết quả chuẩn hóa (e.g., H, D, A)
    
    # Scores
    home_goals: Optional[int]
    away_goals: Optional[int]
    ht_home_goals: Optional[int]
    ht_away_goals: Optional[int]

    # Venue & Referee
    stadium: Optional[ParsedStadium]
    referee: Optional[ParsedReferee]
    
    # --- Business Enrichment Fields ---
    importance: str         # Mức độ quan trọng (e.g., HIGH, MEDIUM)
    
    # --- ML-Ready Fields ---
    status_label: int       # Trạng thái đã được mã hóa (e.g., 2)
    outcome_label: int      # Kết quả đã được mã hóa (e.g., 0, 1, 2)
    
    # Internal ID (sẽ được Loader điền vào)
    internal_id: Optional[int] = None