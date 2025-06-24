# ai-engine/config/business_constants.py

from enum import Enum
from typing import List, Tuple, Dict, FrozenSet
from .core_constants import (
    PlayerPosition, 
    MatchStatus, 
    MatchOutcome,
    API_STATUS_MAPPING,
    API_POSITION_MAPPING,
    API_OUTCOME_MAPPING
)

# ======================== MATCH STATUSES ========================
MatchStatusCategory = MatchStatus
MATCH_STATUS_MAPPING = API_STATUS_MAPPING

# ======================== PLAYER POSITIONS ========================
POSITION_MAPPING = API_POSITION_MAPPING

# ======================== ENTITY TYPES ========================
VALID_ENTITY_TYPES: FrozenSet[str] = frozenset({
    'team', 'player', 'match', 'stadium', 'league', 'referee'
})

# ======================== MATCH OUTCOMES ========================
OUTCOME_MAPPING = API_OUTCOME_MAPPING

# ======================== SEASON CONSTANTS ========================
import datetime
from dateutil import relativedelta
import pytz

now = datetime.datetime.now(pytz.timezone("Europe/London"))
CURRENT_YEAR = now.year

# Xác định mùa giải hiện tại và hoàn thành gần nhất chính xác hơn
if now.month >= 8:  # Mùa giải bắt đầu tháng 8 năm N đến tháng 5 năm N+1
    CURRENT_SEASON = (CURRENT_YEAR, CURRENT_YEAR + 1)
    LAST_COMPLETED_SEASON = (CURRENT_YEAR - 1, CURRENT_YEAR)
else:
    CURRENT_SEASON = (CURRENT_YEAR - 1, CURRENT_YEAR)
    LAST_COMPLETED_SEASON = (CURRENT_YEAR - 2, CURRENT_YEAR - 1)

SEASON_FORMAT: str = "{start}/{end}"

# ======================== SEASONS TO FETCH ========================
# Tạo danh sách mùa giải tự động dựa trên năm hiện tại
SEASONS_TO_FETCH: List[Tuple[int, int]] = []
start_year = 2018
end_year = CURRENT_SEASON[1]

for year in range(start_year, end_year):
    SEASONS_TO_FETCH.append((year, year + 1))

# Đảm bảo có ít nhất 5 mùa giải
if len(SEASONS_TO_FETCH) < 5:
    extra_seasons = 5 - len(SEASONS_TO_FETCH)
    for i in range(1, extra_seasons + 1):
        SEASONS_TO_FETCH.append((start_year - i, start_year - i + 1))

# ======================== ML LABEL MAPPINGS ========================
class MLOutcomeLabels(Enum):
    """Nhãn số cho bài toán dự đoán kết quả trận đấu"""
    HOME_WIN = 0
    DRAW = 1
    AWAY_WIN = 2
    UNKNOWN = -1

    @classmethod
    def from_outcome(cls, outcome: MatchOutcome) -> int:
        mapping = {
            MatchOutcome.HOME: cls.HOME_WIN.value,
            MatchOutcome.DRAW: cls.DRAW.value,
            MatchOutcome.AWAY: cls.AWAY_WIN.value,
            MatchOutcome.UNKNOWN: cls.UNKNOWN.value
        }
        return mapping.get(outcome, cls.UNKNOWN.value)
    
    @classmethod
    def to_outcome(cls, label: int) -> MatchOutcome:
        reverse_mapping = {
            cls.HOME_WIN.value: MatchOutcome.HOME,
            cls.DRAW.value: MatchOutcome.DRAW,
            cls.AWAY_WIN.value: MatchOutcome.AWAY,
            cls.UNKNOWN.value: MatchOutcome.UNKNOWN
        }
        return reverse_mapping.get(label, MatchOutcome.UNKNOWN)

# ======================== FEATURE CATEGORICAL MAPPINGS ========================
# Thêm giá trị UNKNOWN cho các mapping
PLAYER_POSITION_LABELS = {
    PlayerPosition.GK: 0,
    PlayerPosition.DEF: 1,
    PlayerPosition.MID: 2,
    PlayerPosition.FWD: 3,
    PlayerPosition.UNKNOWN: -1  # Bổ sung giá trị UNKNOWN
}

MATCH_STATUS_LABELS = {
    MatchStatus.SCHEDULED: 0,
    MatchStatus.IN_PROGRESS: 1,
    MatchStatus.FINISHED: 2,
    MatchStatus.POSTPONED: 3,
    MatchStatus.CANCELLED: 4,
    MatchStatus.UNKNOWN: -1  # Bổ sung giá trị UNKNOWN
}

# ======================== COMPLETE LABEL MAPPING API ========================
# Cập nhật để xử lý các giá trị UNKNOWN
LABEL_MAPPERS = {
    "match_outcome": {
        "encoder": MLOutcomeLabels.from_outcome,
        "decoder": MLOutcomeLabels.to_outcome
    },
    "player_position": {
        "encoder": lambda pos: PLAYER_POSITION_LABELS.get(pos, PLAYER_POSITION_LABELS[PlayerPosition.UNKNOWN]),
        "decoder": lambda label: next(
            (pos for pos, lbl in PLAYER_POSITION_LABELS.items() if lbl == label), 
            PlayerPosition.UNKNOWN
        )
    },
    "match_status": {
        "encoder": lambda status: MATCH_STATUS_LABELS.get(status, MATCH_STATUS_LABELS[MatchStatus.UNKNOWN]),
        "decoder": lambda label: next(
            (status for status, lbl in MATCH_STATUS_LABELS.items() if lbl == label),
            MatchStatus.UNKNOWN
        )
    }
}

# ======================== ADDITIONAL CONSTANTS ========================
# Thêm các hằng số nghiệp vụ quan trọng
MINUTES_IN_MATCH = 90
EXTRA_TIME_MINUTES = 30
PENALTY_SHOOTOUT_ROUNDS = 5

# Ngưỡng quan trọng cho thống kê
POSSESSION_THRESHOLD = 0.6  # 60% kiểm soát bóng
SHOTS_ON_TARGET_THRESHOLD = 5
CORNERS_THRESHOLD = 7