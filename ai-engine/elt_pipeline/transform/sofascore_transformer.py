# elt_pipeline/transform/sofascore_transformer.py

"""
SofaScore ETL Pipeline: Transformer.
Chịu trách nhiệm chuyển đổi JSON thô thành các object dataclass đã chuẩn hóa.
Hoạt động như một "Rule-based Engine", đọc quy tắc từ các file config.
"""

import logging
from typing import Dict, Any, Optional, List
import copy
import re

# --- Import các thành phần kiến trúc ---
# Data structures
from .data_structures import ParsedMatch, ParsedTeam, ParsedStadium, ParsedReferee, ParsedLeague, ParsedSeason, ParsedPlayer, ParsedMatchEvent
# Utilities
from utils.dict_helpers import get_nested_value, deep_merge_dicts 

# Transformation Rules & Logic
from config.field_mappings import get_field_mapping, get_special_conversions, unified_event_type_mapper, unified_period_mapper,unified_position_mapper, convert_birthdate
from config.core_constants import get_match_status, get_match_outcome, MatchStatus, MatchOutcome
from config.business_constants import MatchBusinessLogic, MLOutcomeLabels, encode_match_status, SeasonBusinessLogic

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

    def transform_match_and_events(
        self,
        raw_summary: Dict[str, Any],
        raw_detail: Optional[Dict[str, Any]] = None,
        raw_events: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[ParsedMatch]:
        """
        Phương thức chính: Biến đổi MỘT TRẬN ĐẤU HOÀN CHỈNH bao gồm cả các sự kiện.
        """
        # --- Phần transform_match (giữ nguyên logic cũ) ---
        if not raw_summary or not isinstance(raw_summary, dict):
            logger.warning("Invalid raw_summary data provided.")
            return None

        merged_data = copy.deepcopy(raw_summary)
        if raw_detail and isinstance(raw_detail, dict):
            merged_data = deep_merge_dicts(merged_data, raw_detail)

        flat_data = self._apply_mapping_rules(merged_data)

        try:
            raw_status_desc = get_nested_value(merged_data, 'status.description')
            status = get_match_status(raw_status_desc, self.api_type) or MatchStatus.UNKNOWN
            raw_outcome_code = get_nested_value(merged_data, 'winnerCode') 
            outcome = get_match_outcome(raw_outcome_code, self.api_type) or MatchOutcome.UNKNOWN
            home_team_name = MatchBusinessLogic.normalize_team_name(flat_data.get('home_team_name'))
            away_team_name = MatchBusinessLogic.normalize_team_name(flat_data.get('away_team_name'))
            if not home_team_name or not away_team_name: raise ValueError("Normalized team names cannot be empty.")
            importance = MatchBusinessLogic.determine_match_importance(home_team_name, away_team_name).value
            status_label = encode_match_status(status)
            outcome_label = MLOutcomeLabels.from_outcome(outcome)
            league_name = flat_data.get('league_name')
            league_country = flat_data.get('league_country')
            if not league_name or not league_country: raise ValueError("League name or country is missing.")
            
            parsed_league = ParsedLeague(name=league_name, country=league_country)
            
            season_name_from_api = flat_data.get('season_name') or flat_data.get('season_year_str')
            start_year = SeasonBusinessLogic.extract_year_from_season(season_name_from_api)
            if start_year is None:
                raise ValueError(f"Cannot determine season year from data: {flat_data}")

            end_year = start_year + 1
            parsed_season = ParsedSeason(name=f"{start_year}/{str(end_year)[-2:]}", start_year=start_year, end_year=end_year, league=parsed_league)            
            stadium = None
            if flat_data.get('venue_name'):
                stadium = ParsedStadium(
                    name=flat_data.get('venue_name'),
                    city=flat_data.get('venue_city'),
                    capacity=flat_data.get('venue_capacity'),
                    timezone=flat_data.get('venue_timezone') 
                )            
            home_team = ParsedTeam(
                external_id=flat_data['home_team_id'], 
                name=home_team_name,
                short_name=get_nested_value(merged_data, 'homeTeam.shortName'),
                logo_url=f"https://api.sofascore.com/api/v1/team/{flat_data['home_team_id']}/image",
                stadium=stadium # Đội nhà thường gắn với sân vận động của trận đấu
            )
            away_team = ParsedTeam(
                external_id=flat_data['away_team_id'], 
                name=away_team_name,
                short_name=get_nested_value(merged_data, 'awayTeam.shortName'),
                logo_url=f"https://api.sofascore.com/api/v1/team/{flat_data['away_team_id']}/image"
)
            referee = None
            raw_referee_id = flat_data.get('referee_id')
            if raw_referee_id:
                try:
                    referee_id = int(raw_referee_id)
                    referee_name = flat_data.get('referee_name')
                    if referee_name: # Chỉ tạo object nếu có cả ID và tên
                        referee = ParsedReferee(external_id=referee_id, name=referee_name)
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert referee_id '{raw_referee_id}' to int. Skipping referee.")

            # Tạo object ParsedMatch trước
            match = ParsedMatch(
                external_id=flat_data['match_id'],
                season=parsed_season,
                match_datetime=flat_data.get('match_timestamp'),
                match_week=str(flat_data.get('round')) if flat_data.get('round') else None,
                home_team=home_team,
                away_team=away_team,
                status=status,
                outcome=outcome,
                home_goals=flat_data.get('home_goals'),
                away_goals=flat_data.get('away_goals'),
                half_time_home_goals=flat_data.get('half_time_home_goals'),
                half_time_away_goals=flat_data.get('half_time_away_goals'),
                stadium=stadium,
                referee=referee,
                importance=importance,
                status_label=status_label,
                outcome_label=outcome_label
            )
            
            if not match.match_datetime: raise ValueError("Match datetime is missing after transformation.")

            # --- Phần transform_events (được tích hợp vào đây) ---
            if raw_events:
                transformed_events = self._transform_single_match_events(raw_events, match.home_team, match.away_team)
                match.events = transformed_events
            
            if match.status == MatchStatus.UNKNOWN:
                logger.warning(f"Match {match.external_id} has an UNKNOWN status and will be skipped.")
                return None

            logger.info(f"Successfully transformed and enriched match {match.external_id} with {len(match.events)} events.")
            return match

        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Failed to transform match data: {e}", exc_info=True, extra={"flat_data": flat_data})
            return None

    def _transform_single_match_events(self, raw_events_data: List[Dict[str, Any]], home_team: ParsedTeam, away_team: ParsedTeam) -> List[ParsedMatchEvent]:
        """
        Private helper: Biến đổi một danh sách các sự kiện thô cho một trận đấu.
        """
        if not raw_events_data: return []
        parsed_events = []
        for event in raw_events_data:
            try:
                # Bước 1: Trích xuất thông tin
                def parse_player_from_event_data(player_data: Optional[Dict], api_type: str) -> Optional[ParsedPlayer]:
                    if not player_data:
                        return None
                    return ParsedPlayer(
                        external_id=player_data.get('id'),
                        name=player_data.get('name'),
                        position=unified_position_mapper(player_data.get('position'), api_type),
                        date_of_birth=convert_birthdate(player_data.get('dateOfBirthTimestamp')),
                        nationality=get_nested_value(player_data, 'country.name'),
                        height=player_data.get('height')
                    )

                player = parse_player_from_event_data(get_nested_value(event, 'player'), self.api_type)
                related_player = parse_player_from_event_data(get_nested_value(event, 'playerOut'), self.api_type)
                
                # Bước 2: Chuẩn hóa bằng mapper chung
                db_event_type = unified_event_type_mapper(get_nested_value(event, 'type'), self.api_type)
                db_period = unified_period_mapper(get_nested_value(event, 'period'), self.api_type)

                if not db_event_type or not db_period:
                    continue # Bỏ qua sự kiện không hợp lệ
                
                team_side_str = get_nested_value(event, 'teamSide')
                event_team = None
                if team_side_str == 'home':
                    event_team = home_team
                elif team_side_str == 'away':
                    event_team = away_team

                # Bước 4: Tạo object ParsedMatchEvent
                parsed_event = ParsedMatchEvent(
                    minute=get_nested_value(event, 'time.minute'),
                    event_type=db_event_type,
                    period=db_period,
                    description=get_nested_value(event, 'text'),
                    player=player,
                    related_player=related_player,
                    team=event_team,
                )
                parsed_events.append(parsed_event)
            except Exception as e:
                logger.error(f"Failed to transform an event: {e}", exc_info=True, extra={"event_data": event})
        return parsed_events