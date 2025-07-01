# elt_pipeline/transform/sofascore_transformer.py

"""
SofaScore ETL Pipeline: Transformer.
Chịu trách nhiệm chuyển đổi JSON thô thành các object dataclass đã chuẩn hóa.
Hoạt động như một "Rule-based Engine", đọc quy tắc từ các file config.
"""

import logging
from typing import Dict, Any, Optional, List

# --- Import các thành phần kiến trúc ---
from .data_structures import (
    ParsedMatch, ParsedTeam, ParsedStadium, ParsedReferee, ParsedLeague,
    ParsedSeason, ParsedPlayer, ParsedMatchEvent
)
from utils.dict_helpers import get_nested_value
from config.field_mappings import (
    get_field_mapping, get_special_conversions, convert_birthdate,
    unified_event_type_mapper, unified_period_mapper, unified_position_mapper,
    unified_match_status_mapper, unified_match_outcome_mapper
)
from config.core_constants import MatchStatus, MatchOutcome
from config.business_constants import (
    MatchBusinessLogic, SeasonBusinessLogic, RefereeBusinessLogic,
    MLOutcomeLabels, encode_match_status
)

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
        self.api_type = api_type
        
        field_map = get_field_mapping(api_type)
        self.conversions = get_special_conversions(api_type)

        # === BƯỚC TỰ KIỂM TRA MAPPING ===
        dest_field_counts = {}
        for source, dest in field_map.items():
            dest_field_counts[dest] = dest_field_counts.get(dest, 0) + 1
        
        # Tìm tất cả các tên đích bị trùng lặp
        duplicates = {dest: count for dest, count in dest_field_counts.items() if count > 1}
        
        if duplicates:
            error_messages = []
            for dest, count in duplicates.items():
                # Tìm lại tất cả các nguồn đang trỏ đến đích bị trùng
                sources = [source for source, d in field_map.items() if d == dest]
                msg = f"Destination field '{dest}' is mapped by {count} sources: {sources}"
                error_messages.append(msg)
                logger.error(msg)
            
            # Ném ra một lỗi rõ ràng để pipeline dừng lại và báo cho bạn biết
            raise ValueError(f"Duplicate field mappings detected! {'; '.join(error_messages)}")
        
        self.field_map = field_map
        logger.info("Field mappings validated successfully. No duplicate destinations found.")

    def _validate_required_fields(self, flat_data: Dict[str, Any]) -> None:
        """
        Validate các field bắt buộc trước khi tạo ParsedMatch.
        """
        required_fields = ['match_id', 'home_team_id', 'away_team_id', 'home_team_name', 'away_team_name']
        missing_fields = [field for field in required_fields if not flat_data.get(field)]
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")

    def _apply_mapping_rules(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Private method: Áp dụng các quy tắc từ `field_mappings.py` để tạo ra một
        dict "phẳng", đã được đổi tên trường và chuyển đổi kiểu dữ liệu cơ bản.
        """
        flat_data = {}
        for source_path, dest_field in self.field_map.items():
            raw_value = get_nested_value(raw_data, source_path)
            
            if source_path in self.conversions:
                try:
                    conversion_func = self.conversions[source_path]
                    flat_data[dest_field] = conversion_func(raw_value)
                except Exception as e:
                    logger.warning(f"Conversion failed for {source_path}: {e}")
                    flat_data[dest_field] = raw_value
            else:
                flat_data[dest_field] = raw_value
        return flat_data

    def transform_match_and_events(
        self,
        raw_match_data: Dict[str, Any],
        raw_events: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[ParsedMatch]:

        if not raw_match_data or not isinstance(raw_match_data, dict):
            logger.warning("Invalid raw_match_data provided.")
            return None

        flat_data = {}
        try:

            print("\n--- DEBUG: RAW MATCH DATA (INPUT) ---")
            import json
            print(json.dumps(raw_match_data.get('homeScore'), indent=2))
            print(json.dumps(raw_match_data.get('awayScore'), indent=2))
            print("---------------------------------------\n")

            # BƯỚC 1: ÁP DỤNG MAPPING - Tạo ra một dict phẳng, đã đổi tên
            flat_data = self._apply_mapping_rules(raw_match_data)

            print("\n--- DEBUG: FLAT DATA (OUTPUT) ---")
            # In ra tất cả các key liên quan đến score
            score_keys = [k for k in flat_data.keys() if 'goal' in k]
            for key in score_keys:
                print(f"{key} from flat_data: {flat_data.get(key)}")
            print("-----------------------------------\n")

            self._validate_required_fields(flat_data)

            # BƯỚC 2: TẠO CÁC OBJECT CON (LEAGUE, SEASON, STADIUM, REFEREE)
            parsed_league = ParsedLeague(
                external_id=self._safe_int_conversion(flat_data.get('league_id')),
                unique_tournament_id=self._safe_int_conversion(flat_data.get('unique_tournament_id')),
                name=flat_data['league_name'],
                country=flat_data['league_country'],
                priority=self._safe_int_conversion(flat_data.get('tournament_priority'))
            )
            
            start_year = SeasonBusinessLogic.extract_year_from_season(
                flat_data.get('season_name') or flat_data.get('season_year_str')
            )
            if start_year is None: raise ValueError("Cannot determine season year.")
            parsed_season = ParsedSeason(
                external_id=self._safe_int_conversion(flat_data.get('season_id')),
                name=f"{start_year}/{str(start_year + 1)[-2:]}",
                start_year=start_year, end_year=start_year + 1, league=parsed_league
            )
            
            match_stadium = ParsedStadium(
                external_id=self._safe_int_conversion(flat_data.get('match_venue_id')),
                name=flat_data.get('match_venue_name'),
                city=flat_data.get('match_venue_city'),
                capacity=self._safe_int_conversion(flat_data.get('match_venue_capacity')),
                latitude=flat_data.get('match_venue_latitude'),
                longitude=flat_data.get('match_venue_longitude'),
            ) if flat_data.get('match_venue_id') else None
            
            referee = ParsedReferee(
                external_id=self._safe_int_conversion(flat_data.get('referee_id')),
                name=flat_data.get('referee_name'),
                country=flat_data.get('referee_country'),
                total_yellow_cards=self._safe_int_conversion(flat_data.get('referee_total_yellow_cards')),
                total_red_cards=self._safe_int_conversion(flat_data.get('referee_total_red_cards')),
                total_yellow_red_cards=self._safe_int_conversion(flat_data.get('referee_total_yellow_red_cards')),
                total_games_officiated=self._safe_int_conversion(flat_data.get('referee_total_games'))
            ) if flat_data.get('referee_id') else None
            
            # BƯỚC 3: TẠO OBJECT TEAM (ĐỘI NHÀ VÀ ĐỘI KHÁCH)
            home_team_stadium = ParsedStadium(
                external_id=self._safe_int_conversion(flat_data.get('home_team_venue_id')),
                name=flat_data.get('home_team_venue_name'),
                city=flat_data.get('home_team_venue_city'),
                capacity=self._safe_int_conversion(flat_data.get('home_team_venue_capacity'))
            ) if flat_data.get('home_team_venue_id') else None

            home_foundation_date = flat_data.get('home_team_established_ts')
            home_team = ParsedTeam(
                external_id=self._safe_int_conversion(flat_data['home_team_id']),
                name=MatchBusinessLogic.normalize_team_name(flat_data.get('home_team_name')),
                short_name=flat_data.get('home_team_short_name'),
                name_code=flat_data.get('home_team_code'),
                full_name=flat_data.get('home_team_full_name'),
                stadium=home_team_stadium,
                established_year=home_foundation_date.year if home_foundation_date else None,
                logo_url=f"https://api.sofascore.com/api/v1/team/{flat_data['home_team_id']}/image",
                fan_count=self._safe_int_conversion(flat_data.get('home_team_fan_count')),
                manager_id=self._safe_int_conversion(flat_data.get('home_team_manager_id')),
                manager_name=flat_data.get('home_team_manager_name'),
                manager_country=flat_data.get('home_team_manager_country'),
                primary_color=flat_data.get('home_team_primary_color'),
                secondary_color=flat_data.get('home_team_secondary_color')
            )
            
            away_foundation_date = flat_data.get('away_team_established_ts')
            away_team = ParsedTeam(
                external_id=self._safe_int_conversion(flat_data['away_team_id']),
                name=MatchBusinessLogic.normalize_team_name(flat_data.get('away_team_name')),
                short_name=flat_data.get('away_team_short_name'),
                name_code=flat_data.get('away_team_code'),
                full_name=flat_data.get('away_team_full_name'),
                stadium=None, # API thường không cung cấp sân nhà của đội khách trong context trận đấu
                established_year=away_foundation_date.year if away_foundation_date else None,
                logo_url=f"https://api.sofascore.com/api/v1/team/{flat_data['away_team_id']}/image",
                fan_count=self._safe_int_conversion(flat_data.get('away_team_fan_count')),
                manager_id=self._safe_int_conversion(flat_data.get('away_team_manager_id')),
                manager_name=flat_data.get('away_team_manager_name'),
                manager_country=flat_data.get('away_team_manager_country'),
                primary_color=flat_data.get('away_team_primary_color'),
                secondary_color=flat_data.get('away_team_secondary_color')
            )

            # BƯỚC 4: LÀM GIÀU DỮ LIỆU (ENRICHMENT)
            status = unified_match_status_mapper(flat_data.get('status_description'), self.api_type) or MatchStatus.UNKNOWN
            outcome = unified_match_outcome_mapper(str(flat_data.get('outcome_code')), self.api_type) or MatchOutcome.UNKNOWN
            
            # Gọi hàm logic nghiệp vụ bằng cách truyền cả object để có thể xử lý sâu hơn
            importance = MatchBusinessLogic.determine_match_importance(home_team, away_team).value
            status_label = encode_match_status(status)
            outcome_label = MLOutcomeLabels.from_outcome(outcome)
            
            # BƯỚC 5: LẮP RÁP OBJECT PARSEDMATCH
            match = ParsedMatch(
                # Các trường bắt buộc
                external_id=self._safe_int_conversion(flat_data.get('match_id')),
                season=parsed_season,
                match_datetime=flat_data.get('match_timestamp'),
                home_team=home_team,
                away_team=away_team,
                status=status,
                importance=importance,
                status_label=status_label,
                outcome_label=outcome_label,
                
                # Các trường tùy chọn
                match_week=str(flat_data.get('round')) if flat_data.get('round') else None,
                attendance=self._safe_int_conversion(flat_data.get('attendance')),
                stadium=match_stadium,
                referee=referee,
                outcome=outcome,
                outcome_code=self._safe_int_conversion(flat_data.get('outcome_code')),
                home_goals=self._safe_int_conversion(flat_data.get('home_goals')),
                away_goals=self._safe_int_conversion(flat_data.get('away_goals')),
                half_time_home_goals=self._safe_int_conversion(flat_data.get('half_time_home_goals')),
                half_time_away_goals=self._safe_int_conversion(flat_data.get('half_time_away_goals')),
                home_goals_normaltime=self._safe_int_conversion(flat_data.get('home_goals_normaltime')),
                away_goals_normaltime=self._safe_int_conversion(flat_data.get('away_goals_normaltime')),
                second_half_home_goals=self._safe_int_conversion(flat_data.get('second_half_home_goals')),
                second_half_away_goals=self._safe_int_conversion(flat_data.get('second_half_away_goals')),
                injury_time_first_half=self._safe_int_conversion(flat_data.get('injury_time_first_half')),
                injury_time_second_half=self._safe_int_conversion(flat_data.get('injury_time_second_half')),
                has_xg=flat_data.get('has_xg'),
                has_event_player_statistics=flat_data.get('has_event_player_statistics'),
                # `events` sẽ được thêm ở bước sau
            )

            # BƯỚC 6: KIỂM TRA TÍNH NHẤT QUÁN & XỬ LÝ SỰ KIỆN
            if match.home_goals is not None and match.away_goals is not None:
                # Luôn tính toán kết quả thực tế từ tỷ số
                actual_outcome = MatchBusinessLogic.determine_outcome_from_score(
                    match.home_goals, match.away_goals
                )
                
                # Kịch bản 1: API không cung cấp kết quả, nhưng chúng ta có thể suy ra từ tỷ số
                if match.outcome == MatchOutcome.UNKNOWN:
                    logger.info(
                        f"Match {match.external_id} has no API outcome, but score is available. "
                        f"Deriving outcome '{actual_outcome.value}' from score {match.home_goals}-{match.away_goals}."
                    )
                    match.outcome = actual_outcome
                    match.outcome_label = MLOutcomeLabels.from_outcome(actual_outcome)
                    
                # Kịch bản 2: API cung cấp kết quả, nhưng nó không khớp với tỷ số
                elif actual_outcome != match.outcome:
                    logger.warning(
                        f"Outcome mismatch for match {match.external_id}: "
                        f"API reports '{match.outcome.value}' but score {match.home_goals}-{match.away_goals} "
                        f"implies '{actual_outcome.value}'. Trusting score-based outcome."
                    )
                    match.outcome = actual_outcome
                    match.outcome_label = MLOutcomeLabels.from_outcome(actual_outcome)

            if raw_events:
                player_cache: Dict[int, ParsedPlayer] = {}
                match.events = self._transform_single_match_events(
                    raw_events, match.home_team, match.away_team, player_cache
                )
                player_cache.clear()

            logger.info(f"Successfully transformed match {match.external_id} with {len(match.events)} events.")
            return match

        except (ValueError, KeyError) as e:
            logger.error(f"Error transforming match {flat_data.get('match_id', 'Unknown')}: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error transforming match {flat_data.get('match_id', 'Unknown')}: {e}", exc_info=True)
            return None

    def _safe_int_conversion(self, value: Any) -> Optional[int]:
        """
        Safely convert value to int, return None if conversion fails.
        """
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Could not convert value '{value}' to int")
            return None

    def _get_or_create_player_from_cache(
        self, 
        player_data: Optional[Dict[str, Any]], 
        player_cache: Dict[int, ParsedPlayer]
    ) -> Optional[ParsedPlayer]:
        """
        Lấy hoặc tạo một object ParsedPlayer sử dụng cache trong phạm vi một trận đấu.
        FIX: Không mutate object trong cache để tránh side effects.
        """
        if not player_data or not isinstance(player_data, dict) or 'id' not in player_data:
            return None
            
        player_id = self._safe_int_conversion(player_data['id'])
        if player_id is None:
            return None

        # Return existing player from cache without mutation
        if player_id in player_cache:
            return player_cache[player_id]

        # Create new player object
        try:
            new_player = ParsedPlayer(
                external_id=player_id,
                name=player_data.get('name'),
                position=unified_position_mapper(player_data.get('position'), self.api_type),
                nationality=get_nested_value(player_data, 'country.name'),
                date_of_birth=convert_birthdate(player_data.get('dateOfBirthTimestamp')),
                height=player_data.get('height')
            )
            
            # Cache the new player
            player_cache[player_id] = new_player
            return new_player
            
        except Exception as e:
            logger.error(f"Failed to create player object: {e}", extra={"player_data": player_data})
            return None
    
    def _transform_single_match_events(
        self,
        raw_events_data: List[Dict[str, Any]],
        home_team: "ParsedTeam",
        away_team: "ParsedTeam",
        player_cache: Dict[int, "ParsedPlayer"]
    ) -> List[ParsedMatchEvent]:
        """
        Private helper: Biến đổi một danh sách các sự kiện thô cho một trận đấu.
        --- PHIÊN BẢN TỐI ƯU VÀ HOÀN THIỆN ---
        - Tuân thủ kiến trúc bằng cách gọi các hàm unified_*_mapper.
        - Xử lý lỗi cho từng sự kiện để tăng độ tin cậy.
        - Giữ lại raw_event_data để phục vụ phân tích sâu.
        """
        if not raw_events_data:
            return []
        
        parsed_events = []
        
        for event_data in raw_events_data:
            try:
                # BƯỚC 1: CHUẨN HÓA CÁC GIÁ TRỊ CỐT LÕI
                event_type = unified_event_type_mapper(get_nested_value(event_data, 'type'), self.api_type)
                period = unified_period_mapper(get_nested_value(event_data, 'period'), self.api_type)

                # Bỏ qua ngay nếu sự kiện không có loại hoặc hiệp đấu hợp lệ
                if not event_type or not period:
                    logger.debug(f"Skipping event due to invalid type or period: {event_data.get('type')}, {event_data.get('period')}")
                    continue
                
                # BƯỚC 2: XỬ LÝ CÁC THỰC THỂ LIÊN QUAN (PLAYER, TEAM)
                
                # Lấy object cầu thủ chính và cầu thủ liên quan (cho việc thay người)
                # Hàm này đã có sẵn logic cache để tối ưu
                player = self._get_or_create_player_from_cache(
                    get_nested_value(event_data, 'player'), player_cache
                )
                related_player = self._get_or_create_player_from_cache(
                    get_nested_value(event_data, 'playerOut'), player_cache
                )
                
                # Xác định đội của sự kiện
                team_side_str = get_nested_value(event_data, 'teamSide')
                event_team = None
                if team_side_str == 'home':
                    event_team = home_team
                elif team_side_str == 'away':
                    event_team = away_team
                
                # BƯỚC 3: LẮP RÁP OBJECT PARSEDEVENT
                
                parsed_event = ParsedMatchEvent(
                    minute=self._safe_int_conversion(get_nested_value(event_data, 'time.minute')),
                    event_type=event_type,
                    period=period,
                    description=get_nested_value(event_data, 'text'),
                    player=player,
                    related_player=related_player,
                    team=event_team,
                    raw_event_data=event_data  # Giữ lại dữ liệu thô để phân tích sâu
                )
                parsed_events.append(parsed_event)
                
            except Exception as e:
                # Nếu có bất kỳ lỗi nào khi xử lý MỘT sự kiện, ghi log và tiếp tục
                # Điều này làm cho pipeline trở nên mạnh mẽ hơn.
                logger.error(
                    f"Failed to transform a single event: {e}",
                    exc_info=True,
                    extra={"event_data": event_data}
                )
                continue
        
        return parsed_events