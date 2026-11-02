# backend/config/core_constants.py

from typing import Optional, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)

VALID_ENTITY_TYPES = frozenset({
    "team", "player", "match", "stadium", "league", "season", "referee"
})


class MatchStatus(str, Enum):
    """
    Định nghĩa các trạng thái chuẩn hóa của một trận đấu.
    Kế thừa từ (str, Enum) cho phép các thành viên của Enum (ví dụ: MatchStatus.SCHEDULED)
    có thể được sử dụng như một chuỗi thông thường (ví dụ: giá trị của nó là "SCHEDULED").
    Điều này rất tiện lợi khi lưu trữ vào cơ sở dữ liệu hoặc tuần tự hóa thành JSON.
    """
    SCHEDULED = "SCHEDULED"         # Trận đấu đã được lên lịch nhưng chưa diễn ra.
    IN_PROGRESS = "IN_PROGRESS"     # Trận đấu đang diễn ra.
    FINISHED = "FINISHED"           # Trận đấu đã kết thúc.
    POSTPONED = "POSTPONED"         # Trận đấu bị hoãn.
    CANCELLED = "CANCELLED"         # Trận đấu bị hủy.
    ABANDONED = "ABANDONED"         # Trận đấu bị dừng giữa chừng và không tiếp tục.

class PlayerPosition(str, Enum):
    """Định nghĩa các vị trí chung của cầu thủ trên sân."""
    GK = "GK"       # Goalkeeper (Thủ môn)
    DEF = "DEF"     # Defender (Hậu vệ)
    MID = "MID"     # Midfielder (Tiền vệ)
    FWD = "FWD"     # Forward (Tiền đạo)

class MatchOutcome(str, Enum):
    """Kết quả trận đấu (Thắng/Hòa/Bại)."""
    H = "H"  # Home win
    D = "D"  # Draw
    A = "A"  # Away win

class PlayerStatus(str, Enum):
    """Định nghĩa trạng thái sẵn sàng thi đấu của một cầu thủ cho một trận đấu cụ thể."""
    AVAILABLE = "Available"                  # Có thể thi đấu
    INJURED = "Injured"                      # Bị chấn thương
    SUSPENDED = "Suspended"                  # Bị treo giò
    QUESTIONABLE = "Questionable"            # Khả năng ra sân bỏ ngỏ (50/50)
    AWAY_ON_INTL_DUTY = "Away on Intl Duty"  # Bận làm nhiệm vụ quốc tế
    MISSING_FIXTURE = "Missing Fixture"      # Vắng mặt vì lý do khác không xác định

class MatchEventType(str, Enum):
    """Các loại sự kiện trong trận đấu."""
    GOAL = 'goal'
    YELLOW_CARD = 'yellow card'
    RED_CARD = 'red card'
    SUBSTITUTION = 'substitution'
    FOUL = 'foul'
    CORNER = 'corner'
    OFFSIDE = 'offside'
    PENALTY = 'penalty'
    OWN_GOAL = 'own goal'
    MISSED_PENALTY = 'missed penalty'
    PENALTY_GOAL = 'penalty goal'
    VAR_DECISION = 'var decision'
    GOAL_CANCELLED = 'goal cancelled'
    PENALTY_CONFIRMED = 'penalty confirmed'
    INJURY = 'injury'
    CORNER_KICK = 'corner kick'
    FREE_KICK = 'free kick'

class MatchPeriod(str, Enum):
    """Các hiệp đấu."""
    FIRST_HALF = '1H'
    SECOND_HALF = '2H'
    EXTRA_TIME_1 = 'ET1'
    EXTRA_TIME_2 = 'ET2'
    PENALTIES = 'PEN'

# --- Các hằng số khác không liên quan trực tiếp đến schema ENUMs ---
class SofascoreWinnerCodes:
    """
    Lớp này dùng như một namespace (không gian tên) để nhóm các hằng số là mã kết quả
    trận đấu từ API của SofaScore. Dùng class thay vì biến toàn cục giúp code gọn gàng,
    có tổ chức hơn.
    """
    HOME_WIN = 1
    AWAY_WIN = 2
    DRAW_TYPE_1 = 3
    DRAW_TYPE_2 = 0

# SofaScore specific constants
class SofascoreConstants:
    """Lớp chứa các ID cụ thể của SofaScore, ví dụ như ID của giải đấu, mùa giải."""
    # Premier League tournament ID
    EPL_TOURNAMENT_ID = 17
    
    # Common season IDs (update these as needed)
    SEASON_IDS = {
        "2017/18": 13380,
        "2018/19": 17359,
        "2019/20": 23776,
        "2020/21": 29415,
        "2021/22": 37036,
        "2022/23": 41886,
        "2023/24": 52186,
        "2024/25": 61627 
    }

# Legacy support - keep for backward compatibility
class BetType:
    UNKNOWN = "Unknown"

BET_TYPE_MAPPING = {}

# --- Dictionaries Mapping từ API về hằng số chuẩn hóa ---
# Ánh xạ các giá trị từ các API (ví dụ: SofaScore) về Enum chuẩn của hệ thống.

# SofaScore status mapping 
SOFASCORE_STATUS_MAPPING: Dict[str, MatchStatus] = {
    # Scheduled statuses
    "notstarted": MatchStatus.SCHEDULED,
    "scheduled": MatchStatus.SCHEDULED,
    
    # In-Play statuses  
    "inprogress": MatchStatus.IN_PROGRESS,
    "1st_half": MatchStatus.IN_PROGRESS,
    "2nd_half": MatchStatus.IN_PROGRESS,
    "halftime": MatchStatus.IN_PROGRESS,
    "extra_time": MatchStatus.IN_PROGRESS,
    "penalties": MatchStatus.IN_PROGRESS,
    "break_time": MatchStatus.IN_PROGRESS,
    "suspended": MatchStatus.IN_PROGRESS,
    "interrupted": MatchStatus.IN_PROGRESS,
    
    # Finished statuses
    "finished": MatchStatus.FINISHED,
    "ended": MatchStatus.FINISHED,
    "after_extra_time": MatchStatus.FINISHED,
    "after_penalties": MatchStatus.FINISHED,
    "awarded": MatchStatus.FINISHED,
    "walkover": MatchStatus.FINISHED,
    
    # Postponed
    "postponed": MatchStatus.POSTPONED,
    
    # Cancelled
    "cancelled": MatchStatus.CANCELLED,
    "canceled": MatchStatus.CANCELLED,
    
    # Abandoned
    "abandoned": MatchStatus.ABANDONED
}

# SofaScore position mapping - keys normalized to lowercase
SOFASCORE_POSITION_MAPPING: Dict[str, PlayerPosition] = {
    # SofaScore dùng chữ cái đầu tiên cho vị trí
    "g": PlayerPosition.GK,
    "d": PlayerPosition.DEF,
    "m": PlayerPosition.MID,
    "f": PlayerPosition.FWD
}

# SofaScore player availability mapping
SOFASCORE_PLAYER_AVAILABILITY_MAPPING: Dict[str, PlayerStatus] = {
    "missing": PlayerStatus.MISSING_FIXTURE,
    "doubtful": PlayerStatus.QUESTIONABLE,
    "injured": PlayerStatus.INJURED,
    "suspended": PlayerStatus.SUSPENDED,
    "questionable": PlayerStatus.QUESTIONABLE,
    "doubt": PlayerStatus.QUESTIONABLE,
}

SOFASCORE_PERIOD_MAPPING: Dict[str, MatchPeriod] = {
    "1": MatchPeriod.FIRST_HALF, 
    "2": MatchPeriod.SECOND_HALF, 
    "3": MatchPeriod.EXTRA_TIME_1,
    "4": MatchPeriod.EXTRA_TIME_2, 
    "5": MatchPeriod.PENALTIES
}

SOFASCORE_EVENT_MAPPING: Dict[str, MatchEventType] = {
    "goal": MatchEventType.GOAL,
    "ownGoal": MatchEventType.OWN_GOAL,
    "penalty": MatchEventType.PENALTY_GOAL,
    "penaltyMissed": MatchEventType.MISSED_PENALTY,
    "yellowCard": MatchEventType.YELLOW_CARD,
    "redCard": MatchEventType.RED_CARD,
    "yellowRed": MatchEventType.RED_CARD, 
    "secondYellow": MatchEventType.RED_CARD, # secondYellow cũng là thẻ đỏ
    "substitution": MatchEventType.SUBSTITUTION,
    "varDecision": MatchEventType.VAR_DECISION,
    "goalCancelled": MatchEventType.GOAL_CANCELLED,
    "penaltyAwarded": MatchEventType.PENALTY_CONFIRMED,
    "injury": MatchEventType.INJURY,
    "cornerKick": MatchEventType.CORNER_KICK,
    "freeKick": MatchEventType.FREE_KICK,
    "offside": MatchEventType.OFFSIDE,
    "foul": MatchEventType.FOUL,
    "corner": MatchEventType.CORNER,
}

# Legacy API-Football mapping (kept for reference/migration)
API_FOOTBALL_STATUS_MAPPING = {
    # Scheduled statuses
    "TBD": MatchStatus.SCHEDULED,   # Time To Be Defined
    "NS": MatchStatus.SCHEDULED,    # Not Started

    # In-Play statuses
    "1H": MatchStatus.IN_PROGRESS,  # First Half
    "2H": MatchStatus.IN_PROGRESS,  # Second Half
    "HT": MatchStatus.IN_PROGRESS,  # Halftime
    "ET": MatchStatus.IN_PROGRESS,  # Extra Time
    "P": MatchStatus.IN_PROGRESS,   # Penalty In Progress
    "BT": MatchStatus.IN_PROGRESS,  # Break Time during extra time
    "LIVE": MatchStatus.IN_PROGRESS,# Live (rare cases)
    "SUSP": MatchStatus.IN_PROGRESS,# Match Suspended (In Play)
    "INT": MatchStatus.IN_PROGRESS, # Match Interrupted (In Play)

    # Finished statuses
    "FT": MatchStatus.FINISHED,     # Match Finished
    "AET": MatchStatus.FINISHED,    # After Extra Time
    "PEN": MatchStatus.FINISHED,    # After Penalty Shootout
    "AWD": MatchStatus.FINISHED,    # Technical Loss / Awarded
    "WO": MatchStatus.FINISHED,     # Walkover

    # Postponed
    "PST": MatchStatus.POSTPONED,   # Postponed

    # Cancelled
    "CANC": MatchStatus.CANCELLED,  # Cancelled

    # Abandoned
    "ABD": MatchStatus.ABANDONED    # Abandoned
}

# Legacy API-Football outcome mapping - keys normalized to lowercase
API_FOOTBALL_OUTCOME_MAPPING = {
    "home": MatchOutcome.H,
    "draw": MatchOutcome.D,
    "away": MatchOutcome.A
}

# Legacy API-Football position mapping - keys normalized to lowercase
API_FOOTBALL_POSITION_MAPPING = {
    "goalkeeper": PlayerPosition.GK,
    "defender": PlayerPosition.DEF,
    "midfielder": PlayerPosition.MID,
    "attacker": PlayerPosition.FWD
}

# Legacy API-Football player availability mapping
API_FOOTBALL_PLAYER_AVAILABILITY_MAPPING = {
    "missing fixture": PlayerStatus.MISSING_FIXTURE,
    "questionable": PlayerStatus.QUESTIONABLE
}

# --- Các hàm Mapping thống nhất - Trả về giá trị chuẩn hóa hoặc None ---

# Unified mapping functions for easy switching between APIs
def get_match_status_from_sofascore(api_status: Optional[str]) -> Optional[MatchStatus]:
    """
    Hàm này nhận vào một chuỗi trạng thái thô từ API SofaScore và trả về
    Enum `MatchStatus` đã được chuẩn hóa.
    - `api_status: Optional[str]`: Tham số đầu vào là một chuỗi, hoặc có thể là None.
    - `-> Optional[MatchStatus]`: Hàm sẽ trả về một đối tượng `MatchStatus` nếu thành công, hoặc `None` nếu thất bại (đầu vào không hợp lệ hoặc không có trong bản đồ).
    """
    if not isinstance(api_status, str) or not api_status.strip(): return None
    return SOFASCORE_STATUS_MAPPING.get(api_status.lower().replace(" ", "_"))

def get_player_position_from_sofascore(api_position: Optional[str]) -> Optional[PlayerPosition]:
    """Chuyển đổi vị trí cầu thủ."""
    if not isinstance(api_position, str) or not api_position.strip(): return None
    return SOFASCORE_POSITION_MAPPING.get(api_position.lower())

def get_match_outcome_from_sofascore(winner_code: Optional[int]) -> Optional[MatchOutcome]:
    """
    Chuyển đổi mã người chiến thắng (winner code) từ SofaScore sang Enum `MatchOutcome`.
    Hàm này dùng câu lệnh `if` thay vì dictionary vì số lượng trường hợp ít và rõ ràng.
    """
    if winner_code == SofascoreWinnerCodes.HOME_WIN: return MatchOutcome.H
    if winner_code == SofascoreWinnerCodes.AWAY_WIN: return MatchOutcome.A
    if winner_code in (SofascoreWinnerCodes.DRAW_TYPE_1, SofascoreWinnerCodes.DRAW_TYPE_2): return MatchOutcome.D
    return None
        
def get_player_availability_from_sofascore(api_status: Optional[str]) -> Optional[PlayerStatus]:
    """Chuyển đổi trạng thái sẵn sàng của cầu thủ từ SofaScore."""    
    if not isinstance(api_status, str) or not api_status.strip(): return None
    return SOFASCORE_PLAYER_AVAILABILITY_MAPPING.get(api_status.lower())

def get_event_type_from_sofascore(api_event: Dict[str, Any]) -> Optional[MatchEventType]:
    """
    Hàm này  nhận vào cả một object sự kiện (dictionary) từ API.
    Lý do là vì để xác định chính xác một sự kiện, đôi khi cần nhiều hơn một trường thông tin.
    """
    if not isinstance(api_event, dict): return None
    # Lấy ra loại sự kiện chính từ trường 'incidentType' trong sofascore.
    incident_type = api_event.get('incidentType')
    if not incident_type: return None

    # Logic đặc biệt cho các trường hợp phức tạp
    if incident_type == 'goal':
        if api_event.get('from') == 'penalty':
            return MatchEventType.PENALTY_GOAL
        if api_event.get('isHome') is not None and 'player' in api_event:
            # Giả định logic xác định Own Goal (cần kiểm tra API)
            # Ví dụ: nếu team_id của sự kiện khác với team_id của cầu thủ
            pass

    result = SOFASCORE_EVENT_MAPPING.get(incident_type)
    
    # Nếu không tìm thấy loại sự kiện trong bản đồ, ghi lại một log ở mức DEBUG
    if not result:
        logger.debug(f"Unknown SofaScore event type: '{incident_type}'")
    return result
    
# def get_period_from_sofascore(api_event: Dict[str, Any]) -> Optional[MatchPeriod]:
#     """Xác định hiệp đấu từ một object sự kiện của SofaScore."""
#     if not isinstance(api_event, dict): return None

#     # SofaScore sử dụng time, reversedPeriodTime, addedTime để xác định hiệp
#     # Đây là logic giả định, cần được kiểm tra với dữ liệu thực tế
#     time = api_event.get('time')
#     if time is None: return None

#     if time <= 45 + api_event.get('injuryTime1', 0): return MatchPeriod.FIRST_HALF
#     if time <= 90 + api_event.get('injuryTime2', 0): return MatchPeriod.SECOND_HALF
#     if time <= 105 + api_event.get('injuryTime3', 0): return MatchPeriod.EXTRA_TIME_1
#     if time <= 120 + api_event.get('injuryTime4', 0): return MatchPeriod.EXTRA_TIME_2
#     # Logic cho PENALTIES cần có thông tin riêng từ API
    
#     # Một cách khác nếu API cung cấp period trực tiếp
#     period_key = api_event.get('period') # Giả sử có trường 'period'
#     if period_key:
#         return SOFASCORE_PERIOD_MAPPING.get(str(period_key))
        
#     return None
