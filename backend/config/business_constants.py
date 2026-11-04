from enum import Enum
from typing import List, Tuple, Dict, Any, Optional
from functools import lru_cache
import re

# Import các ENUM cốt lõi đã được chuẩn hóa
from .core_constants import MatchOutcome, MatchStatus, PlayerPosition

# Giả định có các đối tượng này để type hinting, tránh circular import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from elt_pipeline.transform.data_structures import ParsedTeam, ParsedReferee

import logging
logger = logging.getLogger(__name__)

#  1. Các hằng số nghiệp vụ tĩnh

class BusinessRules:
    """
    Một lớp (class) được dùng như một container  để nhóm các quy tắc nghiệp vụ tĩnh và bất biến của giải đấu.
    Việc dùng class giúp tổ chức code gọn gàng, dễ tìm kiếm hơn là định nghĩa hàng loạt biến toàn cục.
    """
    # Hệ thống điểm
    POINTS_WIN = 3
    POINTS_DRAW = 1
    POINTS_LOSS = 0
    
    # Định nghĩa các đội bóng "Big Six" truyền thống của giải Ngoại hạng Anh.
    # Sử dụng frozenset thay vì list vì:
    # 1. Bất biến (Immutable): Không thể thay đổi sau khi đã tạo, đảm bảo tính toàn vẹn của dữ liệu.
    # 2. Tốc độ truy vấn (Lookup): Kiểm tra một phần tử có trong set hay không (ví dụ: `if "Arsenal" in BIG_SIX_TEAMS:`) nhanh hơn nhiều (O(1)) so với list (O(n)).    
    BIG_SIX_TEAMS = frozenset([
        "Arsenal", "Chelsea", "Liverpool", 
        "Manchester City", "Manchester United", "Tottenham Hotspur" 
    ])
    
    # Ánh xạ để chuẩn hóa tên đội bóng. Rất quan trọng khi dữ liệu được thu thập từ nhiều nguồn khác nhau có thể có tên không nhất quán.
    # Cấu trúc:
    # - Key (khóa): Tên chuẩn, chính thức của đội bóng.
    # - Value (giá trị): Một danh sách (list) các biến thể, tên gọi khác, hoặc nickname của đội đó.
    TEAM_NAME_VARIATIONS: Dict[str, List[str]] = {
        "Manchester City": ["Man City"],
        "Manchester United": ["Man United", "Man Utd"],
        "Arsenal": ["The Gunners"],
        "Chelsea": ["The Blues"],
        "Liverpool": ["The Reds"],
        "Tottenham Hotspur": ["Tottenham", "Spurs"],
        "Aston Villa": ["Villa"],
        "AFC Bournemouth": ["Bournemouth"],
        "Brighton & Hove Albion": ["Brighton"],
        "Wolverhampton Wanderers": ["Wolves", "Wolverhampton"],
        "Newcastle United": ["Newcastle"],
        "West Ham United": ["West Ham"],
        # Thêm các đội khác nếu cần...
    }
    # Định nghĩa các cặp đấu Derby (trận đấu giữa các đối thủ cùng thành phố hoặc có tính cạnh tranh lịch sử cao).
    # Dữ liệu này dùng để xác định mức độ quan trọng của trận đấu.
    DERBY_MATCHES = {
        "North London Derby": ("Arsenal", "Tottenham Hotspur"),
        "Manchester Derby": ("Manchester City", "Manchester United"),
        "Merseyside Derby": ("Liverpool", "Everton"),
    }

# 2. CÁC LỚP LOGIC NGHIỆP VỤ (ENRICHMENT)

class TeamNameNormalizer:
    """
    Logic để chuẩn hóa tên đội bóng và  "làm giàu dữ liệu" (Data Enrichment).
    Tối ưu hóa hiệu suất bằng cách tạo một bản đồ tra cứu ngược (reverse mapping) ngay từ đầu.
    """
    def __init__(self, variation_map: Dict[str, List[str]]):
        """
        Hàm khởi tạo của lớp. Nó sẽ được chạy một lần khi đối tượng được tạo ra.
        Nhiệm vụ chính là xây dựng một bản đồ tra cứu ngược để việc chuẩn hóa diễn ra nhanh chóng.
        """
        self._variation_map = variation_map
        # self._reverse_map: Ánh xạ từ TÊN BIẾN THỂ (viết thường) -> TÊN CHUẨN.
        # Ví dụ: {'man city': 'Manchester City', 'man utd': 'Manchester United', ...}
        self._reverse_map: Dict[str, str] = {}
        for standard_name, variations in self._variation_map.items():
            # Thêm tên chuẩn
            self._reverse_map[standard_name.lower()] = standard_name
            # Thêm các biến thể
            for variation in variations:
                self._reverse_map[variation.lower()] = standard_name

    # Decorator @lru_cache giúp lưu lại kết quả của các lần gọi hàm gần đây nhất.
    # Nếu hàm `normalize` được gọi lại với cùng `team_name`, nó sẽ trả về kết quả đã lưu thay vì thực hiện lại logic.
    # `maxsize=128` có nghĩa là nó sẽ lưu kết quả của 128 tên đội bóng khác nhau gần nhất.
    # Điều này cực kỳ hiệu quả vì trong một luồng xử lý, tên của một đội bóng có thể được chuẩn hóa nhiều lần.    
    @lru_cache(maxsize=128) # Cache kết quả để tăng tốc độ
    def normalize(self, team_name: str) -> str:
        """
        Chuẩn hóa một tên đội bóng đầu vào thành tên chuẩn.
        Hàm này được tối ưu để chạy rất nhanh nhờ vào `_reverse_map` và `lru_cache`.
        """
        if not team_name or not isinstance(team_name, str):
            return "Unknown"
        
        normalized_input = team_name.strip().lower()
        
        # Tìm trong reverse map đã được tối ưu
        standard_name = self._reverse_map.get(normalized_input)
        
        if standard_name:
            return standard_name
        
        # Nếu không tìm thấy, ghi log và trả về tên gốc (đã title case)
        logger.debug(f"Unmapped team name: '{team_name}'. Returning as is.")
        return team_name.strip().title()

# Khởi tạo một instance của Normalizer để sử dụng trong toàn hệ thống
team_name_normalizer = TeamNameNormalizer(BusinessRules.TEAM_NAME_VARIATIONS)


class SeasonBusinessLogic:
    """
    Nhóm các hàm logic liên quan đến việc xử lý thông tin mùa giải.
    Sử dụng @staticmethod vì các hàm này không cần truy cập đến trạng thái của một đối tượng cụ thể (self).
    """
    
    @staticmethod
    def extract_year_from_season(season_name: Optional[str]) -> Optional[int]:
        """Trích xuất năm bắt đầu từ tên mùa giải (ví dụ: "22/23" -> 2022)."""
        if not season_name:
            return None
        
        match = re.search(r'^(\d{2,4})', season_name) # Tìm 2 hoặc 4 chữ số ở đầu
        if match:
            year_str = match.group(1)
            try:
                if len(year_str) == 2:
                    year = int(year_str)
                    return 2000 + year if year < 90 else 1900 + year
                return int(year_str)
            except ValueError:
                return None
        return None

class MatchBusinessLogic:
    """Nhóm các hàm logic nghiệp vụ liên quan đến một trận đấu cụ thể."""
    
    @staticmethod
    def determine_outcome_from_score(home_goals: int, away_goals: int) -> MatchOutcome:
        """
        Suy luận kết quả trận đấu (Thắng/Hòa/Bại) từ tỷ số.
        Trả về một giá trị từ Enum MatchOutcome để đảm bảo tính nhất quán.
        """
        if home_goals > away_goals: return MatchOutcome.H
        if home_goals < away_goals: return MatchOutcome.A
        return MatchOutcome.D

    @staticmethod
    def determine_match_importance(home_team: 'ParsedTeam', away_team: 'ParsedTeam') -> str: # Trả về chuỗi
        """
        Xác định mức độ quan trọng của trận đấu dựa trên các quy tắc đã định nghĩa.
        Là logic làm giàu dữ liệu (data enrichment), tạo ra một thuộc tính mới ('importance').
        Thứ tự kiểm tra từ cao đến thấp:
        """
        home_name = home_team.name
        away_name = away_team.name

        # 1. Ưu tiên cao nhất: Các trận Derby.
        for teams_in_derby in BusinessRules.DERBY_MATCHES.values():
            if home_name in teams_in_derby and away_name in teams_in_derby:
                return "HIGH"
        
        # 2. Tiếp theo: Trận đấu giữa hai đội trong nhóm Big Six.
        if home_name in BusinessRules.BIG_SIX_TEAMS and away_name in BusinessRules.BIG_SIX_TEAMS:
            return "HIGH"
            
        # 3. Mức độ trung bình: Một đội Big Six đá với một đội khác.
        if home_name in BusinessRules.BIG_SIX_TEAMS or away_name in BusinessRules.BIG_SIX_TEAMS:
            return "MEDIUM"
        
        # 4. Mặc định: Các trận còn lại có mức độ quan trọng thấp.
        return "LOW"

# 3. CÁC HẰNG SỐ & MAPPING DÀNH RIÊNG CHO ML 

class MLLabeling:
    """
    Một lớp container chuyên dụng cho tất cả các hằng số và hàm liên quan đến việc gán nhãn (Labeling) cho Machine Learning.
    Việc tách biệt hoàn toàn logic ML ra khỏi logic nghiệp vụ chung giúp cho code dễ bảo trì và module hóa:
    - Phần nghiệp vụ (Business Logic) có thể được tái sử dụng cho các mục đích khác (như API, báo cáo) mà không dính dáng đến ML.
    - Phần ML có thể thay đổi (ví dụ: thay đổi cách gán nhãn) mà không ảnh hưởng đến phần nghiệp vụ.
    """
    
    # --- Định nghĩa nhãn cho KẾT QUẢ TRẬN ĐẤU (OUTCOME) ---
    # Ánh xạ từ Enum `MatchOutcome` sang nhãn số nguyên.
    # Mô hình ML làm việc với số, không phải với chuỗi hay Enum.
    OUTCOME_LABELS: Dict[MatchOutcome, int] = {
        MatchOutcome.H: 0,
        MatchOutcome.D: 1,
        MatchOutcome.A: 2,
    }
    # Tạo bản đồ ngược để giải mã (decode) dự đoán của mô hình từ số về lại Enum.
    OUTCOME_LABELS_REVERSE: Dict[int, MatchOutcome] = {v: k for k, v in OUTCOME_LABELS.items()}
    # Một nhãn đặc biệt (-1) để biểu thị dữ liệu không xác định hoặc bị thiếu.
    UNKNOWN_OUTCOME_LABEL = -1

    @classmethod
    def encode_outcome(cls, outcome: Optional[MatchOutcome]) -> int:
        """Chuyển đổi MatchOutcome Enum thành nhãn số."""
        if outcome is None:
            return cls.UNKNOWN_OUTCOME_LABEL
        return cls.OUTCOME_LABELS.get(outcome, cls.UNKNOWN_OUTCOME_LABEL)

    # --- Định nghĩa nhãn cho PLAYER POSITION ---
    POSITION_LABELS: Dict[PlayerPosition, int] = {
        PlayerPosition.GK: 0,  # Thủ môn
        PlayerPosition.DEF: 1, # Hậu vệ
        PlayerPosition.MID: 2, # Tiền vệ
        PlayerPosition.FWD: 3, # Tiền đạo
    }
    UNKNOWN_POSITION_LABEL = -1

    @classmethod
    def encode_position(cls, position: Optional[PlayerPosition]) -> int:
        """Chuyển đổi PlayerPosition Enum thành nhãn số."""
        if position is None:
            return cls.UNKNOWN_POSITION_LABEL
        return cls.POSITION_LABELS.get(position, cls.UNKNOWN_POSITION_LABEL)

    # --- Định nghĩa nhãn cho TRẠNG THÁI TRẬN ĐẤU (MATCH STATUS) ---
    STATUS_LABELS: Dict[MatchStatus, int] = {
        MatchStatus.SCHEDULED: 0,
        MatchStatus.IN_PROGRESS: 1,
        MatchStatus.FINISHED: 2,
        MatchStatus.POSTPONED: 3,
        MatchStatus.CANCELLED: 4,
        MatchStatus.ABANDONED: 5,
    }
    UNKNOWN_STATUS_LABEL = -1

    @classmethod
    def encode_status(cls, status: Optional[MatchStatus]) -> int:
        """Chuyển đổi MatchStatus Enum thành nhãn số."""
        if status is None:
            return cls.UNKNOWN_STATUS_LABEL
        return cls.STATUS_LABELS.get(status, cls.UNKNOWN_STATUS_LABEL)
