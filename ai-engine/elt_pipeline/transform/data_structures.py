# elt_pipeline/transform/data_structures.py

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from decimal import Decimal

from config.core_constants import MatchStatus, PlayerPosition, MatchOutcome, PlayerStatus, MatchEventType, MatchPeriod

# CÁC ĐỐI TƯỢNG CỐT LÕI (CORE ENTITIES)

@dataclass
class ParsedStadium:
    """Ánh xạ tới bảng `Stadiums`. Dữ liệu chuẩn hóa cho một sân vận động."""
    external_id: int
    name: str
    city: Optional[str] = None
    capacity: Optional[int] = None
    timezone: Optional[str] = None  
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    internal_id: Optional[int] = None

@dataclass
class ParsedTeam:
    """Ánh xạ tới bảng `Teams`. Dữ liệu chuẩn hóa cho một đội bóng."""
    external_id: int
    name: str
    short_name: Optional[str] = None
    stadium: Optional[ParsedStadium] = None 
    established_year: Optional[int] = None
    logo_url: Optional[str] = None 
    name_code: Optional[str] = None
    full_name: Optional[str] = None
    fan_count: Optional[int] = None
    manager_name: Optional[str] = None
    manager_id: Optional[int] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    internal_id: Optional[int] = None
    internal_stadium_id: Optional[int] = None

@dataclass
class ParsedReferee:
    """Ánh xạ tới bảng `Referees`. Dữ liệu chuẩn hóa cho một trọng tài."""
    external_id: int
    name: str
    date_of_birth: Optional[date] = None 
    country: Optional[str] = None
    total_yellow_cards: Optional[int] = None
    total_red_cards: Optional[int] = None
    total_games_officiated: Optional[int] = None
    internal_id: Optional[int] = None

@dataclass
class ParsedPlayer:
    """Ánh xạ tới bảng `Players`. Dữ liệu chuẩn hóa cho một cầu thủ."""
    external_id: int
    name: str
    position: Optional[PlayerPosition] = None
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None
    height: Optional[int] = None 
    internal_id: Optional[int] = None

@dataclass
class ParsedLeague:
    """Ánh xạ tới bảng `Leagues`. Dữ liệu chuẩn hóa cho một giải đấu."""
    external_id: int
    name: str
    country: str
    established_year: Optional[int] = None
    internal_id: Optional[int] = None

@dataclass
class ParsedSeason:
    """Ánh xạ tới bảng `Seasons`. Dữ liệu chuẩn hóa cho một mùa giải."""
    external_id: int
    name: str
    start_year: int
    end_year: int
    league: ParsedLeague
    internal_id: Optional[int] = None
    internal_league_id: Optional[int] = None

# CÁC ĐỐI TƯỢNG LIÊN QUAN ĐẾN TRẬN ĐẤU (MATCH-RELATED ENTITIES)

@dataclass
class ParsedMatch:
    """Ánh xạ tới bảng `Matches`. Dữ liệu cốt lõi của một trận đấu."""
    external_id: int
    season: ParsedSeason
    match_datetime: datetime
    match_week: Optional[str]
    home_team: ParsedTeam
    away_team: ParsedTeam
    stadium: Optional[ParsedStadium]
    referee: Optional[ParsedReferee]
    status: MatchStatus
    outcome: Optional[MatchOutcome]
    home_goals: Optional[int]
    away_goals: Optional[int]
    half_time_home_goals: Optional[int]
    half_time_away_goals: Optional[int]
    attendance: Optional[int] = None
    internal_id: Optional[int] = None
    internal_season_id: Optional[int] = None
    internal_home_team_id: Optional[int] = None
    internal_away_team_id: Optional[int] = None
    internal_stadium_id: Optional[int] = None
    internal_referee_id: Optional[int] = None

@dataclass
class ParsedMatchEvent:
    """Ánh xạ tới bảng `MatchEvents`."""
    minute: Optional[int]
    event_type: MatchEventType
    team: Optional[ParsedTeam] 
    player: Optional[ParsedPlayer] 
    related_player: Optional[ParsedPlayer] 
    period: MatchPeriod
    description: Optional[str] = None
    raw_event_data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ParsedLineup:
    """(MỚI) Ánh xạ tới bảng `Lineups`."""
    player: ParsedPlayer
    team: ParsedTeam
    is_starter: bool
    shirt_number: Optional[int]
    is_captain: bool
    position_in_lineup: Optional[str]

@dataclass
class ParsedSquadAvailability:
    """(MỚI) Ánh xạ tới bảng `SquadAvailability`."""
    player: ParsedPlayer
    team: ParsedTeam
    status: PlayerStatus
    notes: Optional[str] = None 

@dataclass
class ParsedMatchPlayerStats:
    """(MỚI) Ánh xạ tới bảng `MatchPlayerStats`."""
    player: ParsedPlayer
    team: ParsedTeam
    is_starter: bool
    minutes_played: int
    goals: int = 0
    assists: int = 0
    shots: int = 0
    shots_on_target: int = 0
    passes: int = 0
    accurate_passes: int = 0
    key_passes: int = 0
    tackles: int = 0
    interceptions: int = 0
    fouls_committed: int = 0
    fouls_drawn: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    saves: int = 0
    substituted_in_minute: Optional[int] = None
    substituted_out_minute: Optional[int] = None

@dataclass
class ParsedMatchTeamStats:
    """(MỚI) Ánh xạ tới bảng `MatchTeamStats`."""
    team: ParsedTeam
    possession_percentage: Optional[Decimal] = None
    total_shots: int = 0
    shots_on_target: int = 0
    shots_off_target: int = 0
    blocked_shots: int = 0
    fouls_committed: int = 0
    corners: int = 0
    offsides: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    saves: int = 0


# ĐỐI TƯỢNG GÓI DỮ LIỆU TỔNG HỢP (THE BUNDLE)

@dataclass
class ParsedMatchBundle:
    """
    Đây là đối tượng trung tâm, gói tất cả dữ liệu đã được chuẩn hóa cho một trận đấu.
    Lớp Transform sẽ tạo ra MỘT đối tượng này.
    Lớp Load sẽ tiêu thụ MỘT đối tượng này.
    """
    match: ParsedMatch
    events: List[ParsedMatchEvent] = field(default_factory=list)
    lineups: List[ParsedLineup] = field(default_factory=list)
    squad_availability: List[ParsedSquadAvailability] = field(default_factory=list)
    player_stats: List[ParsedMatchPlayerStats] = field(default_factory=list)
    team_stats: List[ParsedMatchTeamStats] = field(default_factory=list)