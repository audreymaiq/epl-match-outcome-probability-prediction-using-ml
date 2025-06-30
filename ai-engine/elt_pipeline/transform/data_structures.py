# elt_pipeline/transform/data_structures.py

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List
from dataclasses import dataclass

"""
Định nghĩa các cấu trúc dữ liệu (schemas) đã được chuẩn hóa.
Đây là output của Transformer và là input của Loader.
"""
@dataclass
class ParsedStadium:
    """Dữ liệu chuẩn hóa cho một sân vận động."""
    name: str
    city: Optional[str]
    capacity: Optional[int]
    timezone: Optional[str] = None
    internal_id: Optional[int] = None  

@dataclass
class ParsedTeam:
    """Dữ liệu chuẩn hóa cho một đội bóng."""
    external_id: int
    name: str
    short_name: Optional[str] = None
    stadium: Optional[ParsedStadium] = None
    established_year: Optional[int] = None 
    logo_url: Optional[str] = None
    internal_id: Optional[int] = None  # Sẽ được Loader điền vào

@dataclass
class ParsedReferee:
    """Dữ liệu chuẩn hóa cho một trọng tài."""
    external_id: int
    name: str
    date_of_birth: Optional[date] = None
    country: Optional[str] = None
    internal_id: Optional[int] = None  

@dataclass
class ParsedLeague:
    name: str
    country: str
    established_year: Optional[int] = None
    internal_id: Optional[int] = None

@dataclass
class ParsedSeason:
    name: str        
    start_year: int
    end_year: int
    league: ParsedLeague
    internal_id: Optional[int] = None

@dataclass
class ParsedPlayer:
    """Dữ liệu chuẩn hóa cơ bản cho một cầu thủ."""
    external_id: int
    name: str
    position: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None
    height: Optional[int] = None
    internal_id: Optional[int] = None

@dataclass
class ParsedMatchEvent:
    """Dữ liệu chuẩn hóa cho một sự kiện trong trận đấu."""
    minute: Optional[int]
    event_type: str  
    period: str      
    description: Optional[str] = None
    
    # Thông tin về đội và cầu thủ liên quan
    player: Optional[ParsedPlayer] = None
    related_player: Optional[ParsedPlayer] = None
    team: Optional[ParsedTeam] = None 

    # Các ID nội bộ, sẽ được loader điền vào trước khi ghi vào DB
    internal_match_id: Optional[int] = None
    internal_team_id: Optional[int] = None
    internal_player_id: Optional[int] = None
    internal_related_player_id: Optional[int] = None

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
    match_week: Optional[str]
    
    # Teams
    home_team: ParsedTeam
    away_team: ParsedTeam
    
    # Status & Outcome
    status: str             # Trạng thái chuẩn hóa (e.g., FINISHED)
    outcome: Optional[str]            # Kết quả chuẩn hóa (e.g., H, D, A)
    
    # Scores
    home_goals: Optional[int]
    away_goals: Optional[int]
    half_time_home_goals: Optional[int]
    half_time_away_goals: Optional[int]

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

    events: List[ParsedMatchEvent] = field(default_factory=list)