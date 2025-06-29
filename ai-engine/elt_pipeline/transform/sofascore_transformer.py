# elt_pipeline/transform/sofascore_transformer.py

"""
SofaScore ETL Pipeline: Transformer.
Chịu trách nhiệm chuyển đổi JSON thô thành các object dataclass đã chuẩn hóa.
Hoạt động như một "Rule-based Engine", đọc quy tắc từ các file config.
"""

import logging
from typing import Dict, Any, Optional
import copy

# --- Import các thành phần kiến trúc ---
# Data structures
from .data_structures import ParsedMatch, ParsedTeam, ParsedStadium, ParsedReferee, ParsedLeague, ParsedSeason

# Utilities
from utils.dict_helpers import get_nested_value, deep_merge_dicts 

# Transformation Rules & Logic
from config.field_mappings import get_field_mapping, get_special_conversions
from config.core_constants import get_match_status, get_match_outcome
from config.business_constants import MatchBusinessLogic, MLOutcomeLabels, encode_match_status

logger = logging.getLogger(__name__)

class SofaScoreTransformer:
    """
    Chuyển đổi dữ liệu thô từ SofaScore API thành các đối tượng dữ liệu có cấu trúc,
    đã được làm sạch, chuẩn hóa và làm giàu (enriched).
    """

    def __init__(self, api_type: str = 'sofascore'):
        """
        Khởi tạo Transformer và nạp các bộ quy tắc từ file cấu hình một lần duy nhất.
        """
        logger.info(f"Initializing SofaScoreTransformer for api_type='{api_type}'")
        # Nạp bộ quy tắc ánh xạ trường và chuyển đổi kiểu dữ liệu
        self.field_map = get_field_mapping(api_type)
        self.conversions = get_special_conversions(api_type)
        self.api_type = api_type

    def _apply_mapping_rules(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Private method: Áp dụng các quy tắc từ `field_mappings.py` để tạo ra một
        dict "phẳng", đã được đổi tên trường và chuyển đổi kiểu dữ liệu cơ bản.
        """
        flat_data = {}
        for source_path, dest_field in self.field_map.items():
            # Lấy giá trị từ dict lồng nhau một cách an toàn
            raw_value = get_nested_value(raw_data, source_path)
            
            # Áp dụng hàm chuyển đổi đặc biệt nếu được định nghĩa
            if source_path in self.conversions:
                conversion_func = self.conversions[source_path]
                flat_data[dest_field] = conversion_func(raw_value)
            else:
                flat_data[dest_field] = raw_value
        return flat_data

    def transform_match(
        self, 
        raw_summary: Dict[str, Any], 
        raw_detail: Optional[Dict[str, Any]] = None
    ) -> Optional[ParsedMatch]:
        """
        Phương thức chính: Biến đổi một trận đấu từ dữ liệu thô.
        
        Quy trình:
        1. Gộp dữ liệu tóm tắt và chi tiết (nếu có).
        2. Áp dụng các quy tắc ánh xạ và chuyển đổi cơ bản.
        3. Chuẩn hóa và làm giàu dữ liệu bằng các quy tắc nghiệp vụ.
        4. Xây dựng các đối tượng dataclass đã được chuẩn hóa.
        
        Args:
            raw_summary: Dữ liệu trận đấu từ endpoint danh sách.
            raw_detail: Dữ liệu chi tiết trận đấu từ endpoint chi tiết.
            
        Returns:
            Một đối tượng `ParsedMatch` đã hoàn chỉnh, hoặc `None` nếu lỗi.
        """
        if not raw_summary or not isinstance(raw_summary, dict):
            logger.warning("Invalid raw_summary data provided.")
            return None

        # Bước 1: Gộp dữ liệu chi tiết vào dữ liệu tóm tắt
        merged_data = copy.deepcopy(raw_summary)
        if raw_detail and isinstance(raw_detail, dict):
            merged_data = deep_merge_dicts(merged_data, raw_detail)

        # Bước 2: Áp dụng các quy tắc ánh xạ và chuyển đổi cơ bản
        flat_data = self._apply_mapping_rules(merged_data)

        try:
            # Bước 3: Chuẩn hóa và làm giàu dữ liệu bằng logic nghiệp vụ
            
            # 3.1. Chuẩn hóa Status & Outcome (dùng core_constants)
            raw_status_desc = get_nested_value(merged_data, 'status.description')
            status = get_match_status(raw_status_desc, self.api_type)
            
            raw_outcome_code = get_nested_value(merged_data, 'winnerCode')
            outcome = get_match_outcome(raw_outcome_code, self.api_type)
            
            # 3.2. Chuẩn hóa tên đội bóng (dùng business_constants)
            home_team_name = MatchBusinessLogic.normalize_team_name(flat_data.get('home_team_name'))
            away_team_name = MatchBusinessLogic.normalize_team_name(flat_data.get('away_team_name'))

            if not home_team_name or not away_team_name:
                raise ValueError("Normalized team names cannot be empty.")

            # 3.3. Làm giàu thông tin nghiệp vụ (dùng business_constants)
            importance = MatchBusinessLogic.determine_match_importance(home_team_name, away_team_name).value
            
            # 3.4. Mã hóa cho Machine Learning (dùng business_constants)
            status_label = encode_match_status(status)
            outcome_label = MLOutcomeLabels.from_outcome(outcome)

            # Bước 4: Xây dựng các đối tượng dataclass chuẩn hóa
            league_name = flat_data.get('league_name')
            league_country = flat_data.get('league_country')
            if not league_name or not league_country:
                raise ValueError("League name or country is missing.")

            parsed_league = ParsedLeague(name=league_name, country=league_country)
            
            # Ưu tiên dùng trường "season_year_str" đã được map
            season_year_string = flat_data.get('season_year_str') # Ví dụ: "2023/2024"
            if season_year_string and '/' in season_year_string:
                # Logic chuẩn khi có "2023/2024"
                start_year_str = season_year_string.split('/')[0]
                start_year = int(start_year_str)
            else:
                # Fallback: Dùng regex để tìm một số có 4 chữ số (năm) trong tên mùa giải
                import re
                logger.warning(f"Using fallback for season year. Raw season name: {flat_data.get('season_name')}")
                # Tìm một số có 4 chữ số, ví dụ 2023, 2024...
                match = re.search(r'\b(20\d{2})\b', flat_data.get('season_name', ''))
                if match:
                    start_year = int(match.group(1))
                else:
                    # Nếu không tìm thấy năm, báo lỗi
                    raise ValueError(f"Cannot determine season year from data: {flat_data}")

            end_year = start_year + 1

            parsed_season = ParsedSeason(
                name=f"{start_year}/{str(end_year)[-2:]}", # Chuẩn hóa thành dạng "2023/24"
                start_year=start_year,
                end_year=end_year,
                league=parsed_league
            )            
            
            home_team = ParsedTeam(
                external_id=flat_data['home_team_id'], 
                name=home_team_name
            )
            away_team = ParsedTeam(
                external_id=flat_data['away_team_id'], 
                name=away_team_name
            )
            
            stadium = ParsedStadium(
                name=flat_data.get('venue_name'),
                city=flat_data.get('venue_city'),
                capacity=flat_data.get('venue_capacity')
            ) if flat_data.get('venue_name') else None
            
            referee = ParsedReferee(
                external_id=flat_data.get('referee_id'),
                name=flat_data.get('referee_name')
            ) if flat_data.get('referee_id') else None

            # Tạo đối tượng ParsedMatch cuối cùng
            match = ParsedMatch(
                external_id=flat_data['match_id'],
                season=parsed_season,
                match_datetime=flat_data.get('match_timestamp'),
                round=flat_data.get('round'),
                home_team=home_team,
                away_team=away_team,
                status=status,
                outcome=outcome,
                home_goals=flat_data.get('home_goals'),
                away_goals=flat_data.get('away_goals'),
                ht_home_goals=flat_data.get('half_time_home_goals'),
                ht_away_goals=flat_data.get('half_time_away_goals'),
                stadium=stadium,
                referee=referee,
                importance=importance,
                status_label=status_label,
                outcome_label=outcome_label,
            )
            
            # Kiểm tra các điều kiện bắt buộc cuối cùng
            if not match.match_datetime:
                raise ValueError("Match datetime is missing after transformation.")

            logger.info(f"Successfully transformed and enriched match {match.external_id}")
            return match

        except (KeyError, TypeError, ValueError) as e:
            logger.error(
                f"Failed to transform match due to validation error: {e}", 
                exc_info=True,
                extra={"flat_data": flat_data}
            )
            return None