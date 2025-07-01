# elt_pipeline/transform/data_structures.py

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from config.core_constants import MatchOutcome, MatchStatus, PlayerPosition, MatchEventType, MatchPeriod

"""
Định nghĩa các cấu trúc dữ liệu (schemas) đã được chuẩn hóa.
Đây là output của Transformer và là input của Loader.
"""
@dataclass
class ParsedStadium:
    """Dữ liệu chuẩn hóa cho một sân vận động."""
    external_id: int
    name: str
    city: Optional[str] = None
    capacity: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    internal_id: Optional[int] = None

@dataclass
class ParsedTeam:
    """Dữ liệu chuẩn hóa cho một đội bóng."""
    external_id: int
    name: str
    short_name: Optional[str] = None
    name_code: Optional[str] = None
    full_name: Optional[str] = None
    stadium: Optional[ParsedStadium] = None
    established_year: Optional[int] = None
    logo_url: Optional[str] = None
    fan_count: Optional[int] = None       
    
    # Manager Info
    manager_name: Optional[str] = None
    manager_id: Optional[int] = None
    manager_country: Optional[str] = None     
    
    # Team Colors
    primary_color: Optional[str] = None     
    secondary_color: Optional[str] = None      
    
    internal_id: Optional[int] = None

@dataclass
class ParsedReferee:
    """Dữ liệu chuẩn hóa cho một trọng tài."""
    external_id: int
    name: str
    country: Optional[str] = None
    
    # Historical stats of the referee
    total_yellow_cards: Optional[int] = None   
    total_red_cards: Optional[int] = None
    total_yellow_red_cards: Optional[int] = None 
    total_games_officiated: Optional[int] = None 
    
    internal_id: Optional[int] = None  

@dataclass
class ParsedLeague:
    """Dữ liệu chuẩn hóa cho một giải đấu."""
    external_id: int
    name: str
    country: str                       
    unique_tournament_id: Optional[int] = None  
    priority: Optional[int] = None           
    internal_id: Optional[int] = None

@dataclass
class ParsedSeason:
    """Dữ liệu chuẩn hóa cho một mùa giải."""
    external_id: int            
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
    position: Optional[PlayerPosition] = None
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None
    internal_id: Optional[int] = None

@dataclass
class ParsedMatchEvent:
    """Dữ liệu chuẩn hóa cho một sự kiện trong trận đấu."""
    minute: Optional[int]
    event_type: MatchEventType  
    period: MatchPeriod      
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

    raw_event_data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ParsedMatch:
    """
    Dữ liệu chuẩn hóa hoàn chỉnh cho một trận đấu, được làm giàu cho ML.
    """
    # === Core IDs and Metadata ===
    # === Các trường bắt buộc (không có giá trị mặc định) ===
    external_id: int
    season: ParsedSeason
    match_datetime: datetime
    home_team: ParsedTeam
    away_team: ParsedTeam
    status: MatchStatus
    importance: str
    status_label: int
    outcome_label: int

    # === Các trường tùy chọn (có giá trị mặc định là None hoặc factory) ===
    match_week: Optional[str] = None
    stadium: Optional[ParsedStadium] = None
    referee: Optional[ParsedReferee] = None
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None
    outcome: Optional[MatchOutcome] = None
    events: List[ParsedMatchEvent] = field(default_factory=list)
    attendance: Optional[int] = None
    outcome_code: Optional[int] = None
    half_time_home_goals: Optional[int] = None
    half_time_away_goals: Optional[int] = None
    second_half_home_goals: Optional[int] = None
    second_half_away_goals: Optional[int] = None
    home_goals_normaltime: Optional[int] = None
    away_goals_normaltime: Optional[int] = None
    injury_time_first_half: Optional[int] = None
    injury_time_second_half: Optional[int] = None
    has_xg: Optional[bool] = None
    has_event_player_statistics: Optional[bool] = None
    internal_id: Optional[int] = None