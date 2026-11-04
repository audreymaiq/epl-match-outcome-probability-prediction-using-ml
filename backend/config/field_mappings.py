from datetime import datetime, date
import pytz
from dateutil import parser
import logging
from typing import Dict, Any, Optional, Union, Callable
from decimal import Decimal

# Import các hàm và Enum từ các file cấu hình khác đã được chuẩn hóa
from .core_constants import MatchStatus, PlayerPosition, MatchOutcome, PlayerStatus, MatchEventType, MatchPeriod
from .settings import get_config

# Khi xem log, chúng ta sẽ biết ngay thông báo này đến từ file `field_mappings.py`.
logger = logging.getLogger(__name__)

# SOFASCORE: ÁNH XẠ TÊN TRƯỜNG (FIELD NAME MAPPINGS)

# 1. Mapping cho các trường dữ liệu chính của trận đấu (từ gốc của JSON)
SOFASCORE_MATCH_FIELD_MAPPING: Dict[str, str] = {
    # Match Core & Metadata
    "id": "match_external_id",
    "startTimestamp": "match_timestamp",
    "status.description": "status_description",
    "roundInfo.round": "match_week",
    "winnerCode": "outcome_code",
    "attendance": "attendance",

    "homeScore.normaltime": "home_goals",
    "awayScore.normaltime": "away_goals",
    "homeScore.period1": "half_time_home_goals",
    "awayScore.period1": "half_time_away_goals",

    # League and Season
    "tournament.id": "league_external_id",
    "tournament.name": "league_name",
    "tournament.category.name": "league_country",
    "season.id": "season_external_id",
    "season.name": "season_name",
    "season.year": "season_year_str",

    # Home Team
    "homeTeam.id": "home_team_external_id",
    "homeTeam.name": "home_team_name",

    # Away Team
    "awayTeam.id": "away_team_external_id",
    "awayTeam.name": "away_team_name",

    # Match Venue
    "venue.id": "stadium_external_id",
    "venue.name": "stadium_name",
    "venue.city.name": "stadium_city",
    "venue.capacity": "stadium_capacity",
    "venue.venueCoordinates.latitude": "stadium_latitude",
    "venue.venueCoordinates.longitude": "stadium_longitude",

    "referee.id": "referee_external_id",
    "referee.name": "referee_name",
    "referee.country.name": "referee_country",
    "referee.games": "referee_total_games_officiated",
}

# 2. Mapping cho các trường chi tiết của một cầu thủ (trong mục lineups)
SOFASCORE_PLAYER_DETAILS_MAPPING: Dict[str, str] = {
    "player.id": "player_external_id",
    "player.name": "player_name",
    "player.position": "position_char",  # 'G', 'D', 'M', 'F'
    "player.dateOfBirthTimestamp": "dob_timestamp",
    "player.country.name": "nationality",
    "player.height": "height_cm",
    "shirtNumber": "shirt_number",
    "substitute": "is_substitute", # Dùng để suy ra is_starter
    "captain": "is_captain",
}

# 3. Mapping cho các chỉ số thống kê của cầu thủ (trong lineups -> player -> statistics)
SOFASCORE_PLAYER_STATS_MAPPING: Dict[str, str] = {
    "minutesPlayed": "minutes_played",
    "goals": "goals",
    "goalAssist": "assists",
    "totalScoringAttempt": "shots",
    "onTargetScoringAttempt": "shots_on_target",
    "totalPass": "passes",
    "accuratePass": "accurate_passes",
    "keyPass": "key_passes",
    "totalTackle": "tackles",
    "interceptionWon": "interceptions",
    "fouls": "fouls_committed",
    "wasFouled": "fouls_drawn",
    "yellowCard": "yellow_cards", 
    "redCard": "red_cards",     
    "saves": "saves",
}

# 4. Mapping cho các chỉ số thống kê của đội (trong mục statistics.statistics)
SOFASCORE_TEAM_STATS_MAPPING: Dict[str, str] = {
    "ballPossession": "possession_percentage",
    "totalShotsOnGoal": "total_shots",
    "shotsOnGoal": "shots_on_target",
    "shotsOffGoal": "shots_off_target",
    "blockedScoringAttempt": "blocked_shots",
    "fouls": "fouls_committed",
    "cornerKicks": "corners",
    "offsides": "offsides",
    "goalkeeperSaves": "saves",
    "yellowCards": "yellow_cards", 
    "redCards": "red_cards",    
}

# CÁC HÀM CHUYỂN ĐỔI (CONVERSION FUNCTIONS)

def convert_timestamp_to_utc_datetime(timestamp: Optional[Union[int, float]]) -> Optional[datetime]:
    """
    Chuyển đổi Unix timestamp (số giây từ 1/1/1970) thành đối tượng datetime có nhận biết múi giờ UTC.
    - Input: Một số nguyên hoặc số thực (ví dụ: 1672531200).
    - Output: Một đối tượng datetime (ví dụ: datetime(2023, 1, 1, 0, 0, tzinfo=<UTC>)) hoặc None nếu lỗi.
    - Tại sao UTC?: Chuẩn hóa tất cả thời gian về một múi giờ duy nhất (UTC) là cực kỳ quan trọng để tránh nhầm lẫn và sai sót khi làm việc với dữ liệu từ nhiều nguồn hoặc trên các server khác nhau.
    """
    if timestamp is None: return None
    try:
        return datetime.fromtimestamp(timestamp, tz=pytz.UTC)
    except (OSError, TypeError, ValueError) as e:
        logger.warning(f"Failed to convert timestamp '{timestamp}' to datetime: {e}")
        return None

def convert_timestamp_to_date(timestamp: Optional[Union[int, float]]) -> Optional[date]:
    """
    Chuyển đổi Unix timestamp thành đối tượng date (chỉ lấy ngày, không lấy giờ).
    - Logic: Tái sử dụng hàm trên để lấy đối tượng datetime, sau đó chỉ trả về phần ngày (.date()).
    - Ứng dụng: Hữu ích cho việc lưu ngày sinh, không cần quan tâm đến giờ sinh.
    """
    dt = convert_timestamp_to_utc_datetime(timestamp)
    return dt.date() if dt else None

def convert_possession_to_decimal(value: Optional[str]) -> Optional[Decimal]:
    """
    Chuyển đổi chuỗi phần trăm (ví dụ: '60%') thành số Decimal (ví dụ: 60.00).
    - Input: Một chuỗi như "55%".
    - Output: Một đối tượng Decimal như Decimal('55').
    - Tại sao Decimal?: Sử dụng Decimal thay vì float để tránh các lỗi làm tròn không mong muốn. Điều này quan trọng khi thực hiện các phép tính tài chính hoặc thống kê cần độ chính xác cao.
    """
    if value is None: return None
    try:
        # Loại bỏ ký tự '%' và chuyển thành Decimal để giữ độ chính xác
        return Decimal(str(value).rstrip('%'))
    except (ValueError, TypeError):
        return None

# ÁNH XẠ CHUYỂN ĐỔI ĐẶC BIỆT (SPECIAL CONVERSIONS MAPPING)
# Liên kết TÊN TRƯỜNG NỘI BỘ (đã được dịch từ mapping ở trên) với HÀM CHUYỂN ĐỔI tương ứng.

SOFASCORE_SPECIAL_CONVERSIONS: Dict[str, Callable] = {
    # Tên trường nội bộ         # Hàm sẽ được gọi để xử lý giá trị của trường đó
    "match_timestamp":           convert_timestamp_to_utc_datetime,
    "dob_timestamp":             convert_timestamp_to_date,
    "possession_percentage":     convert_possession_to_decimal,
}
