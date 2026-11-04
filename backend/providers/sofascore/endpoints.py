import re
from enum import Enum
from functools import lru_cache
from typing import Set

class SofaScoreEndpoints(Enum):
    """
    Định nghĩa các đường dẫn (endpoints) API của SofaScore dưới dạng một Enum.
    Mỗi thành viên của Enum này là một hằng số đại diện cho một endpoint cụ thể.

    Thiết kế với placeholder:
    Các chuỗi URL chứa các "placeholder" (trình giữ chỗ) được bao trong dấu ngoặc nhọn,
    ví dụ: `{match_id}`, `{season_id}`.
    Kỹ thuật này  cho phép tái sử dụng các mẫu URL này. Một lớp khác
    (như `Extractor` được gợi ý trong docstring) sẽ chịu trách nhiệm lấy giá trị thực tế
    (ví dụ: match_id = 12345) và thay thế vào placeholder này để tạo ra URL hoàn chỉnh.
    """
    
    # === Core Match Endpoints ===
    MATCH_DETAIL = "/event/{match_id}"
    MATCH_LINEUPS = "/event/{match_id}/lineups"  
    MATCH_STATISTICS = "/event/{match_id}/statistics"
    MATCH_INCIDENTS = "/event/{match_id}/incidents"
    TOURNAMENT_SEASONS = "/unique-tournament/{tournament_id}/seasons"
    
    # === Season-specific Endpoints ===
    SEASON_STANDINGS = "/unique-tournament/{tournament_id}/season/{season_id}/standings/total"
    SEASON_MATCHES_LAST = "/unique-tournament/{tournament_id}/season/{season_id}/events/last/{page}"
    SEASON_MATCHES_NEXT = "/unique-tournament/{tournament_id}/season/{season_id}/events/next/{page}"
    SEASON_TOP_PLAYERS = "/unique-tournament/{tournament_id}/season/{season_id}/top-players/{type}"
    
    # === Team Endpoints ===
    TEAM_INFO = "/team/{team_id}"
    TEAM_MATCHES_LAST = "/team/{team_id}/events/last/{page}"
    TEAM_MATCHES_NEXT = "/team/{team_id}/events/next/{page}"
    
    # === Player Endpoints ===
    PLAYER_INFO = "/player/{player_id}"
    PLAYER_MATCHES = "/player/{player_id}/events/last/{page}"

    @lru_cache(maxsize=None)
    def get_required_params(self) -> Set[str]:
        """
        Tự động xác định các tham số (parameters) bắt buộc mà một đường dẫn API (endpoint) cần để có thể hoạt động.
        Phân tích chuỗi URL của thành viên Enum và trả về một tập hợp (set)
        chứa tên của tất cả các tham số (placeholder) bắt buộc có trong đó.

        Ví dụ:
        - Input: self.value (chuỗi URL) của `MATCH_DETAIL` là "/event/{match_id}"
        - Output: một set là `{'match_id'}`

        - Input: self.value của `SEASON_STANDINGS`
        - Output: một set là `{'tournament_id', 'season_id'}`

        Returns:
            Set[str]: Một tập hợp các chuỗi, mỗi chuỗi là tên của một tham số.
                    Sử dụng `Set` thay vì `List` vì nó đảm bảo các phần tử là duy nhất
                    và việc kiểm tra một phần tử có trong set hay không (`in`) rất nhanh.
        """
        # Nhận vào chuỗi URL (ví dụ: /.../{tournament_id}/.../{season_id}/.../{page}).
        # Dùng biểu thức chính quy (Regular Expression) r'\{(\w+)\}' để tìm tất cả các chuỗi nằm trong cặp dấu ngoặc nhọn {...}.
        # Trích xuất những cái tên bên trong đó (chính là tournament_id, season_id, page).
        # Trả về một Set (tập hợp) chứa các tên này: {'tournament_id', 'season_id', 'page'}.        
        
        return set(re.findall(r'\{(\w+)\}', self.value))
