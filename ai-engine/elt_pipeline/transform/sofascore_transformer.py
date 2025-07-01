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
from .data_structures import ParsedMatch, ParsedTeam, ParsedStadium, ParsedReferee, ParsedLeague, ParsedSeason, ParsedPlayer, ParsedMatchEvent
from utils.dict_helpers import get_nested_value, deep_merge_dicts 
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
        self.field_map = get_field_mapping(api_type)
        self.conversions = get_special_conversions(api_type)
        self.api_type = api_type

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
        raw_summary: Dict[str, Any],
        raw_detail: Optional[Dict[str, Any]] = None,
        raw_events: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[ParsedMatch]:
        """
        Phương thức chính: Biến đổi MỘT TRẬN ĐẤU HOÀN CHỈNH bao gồm cả các sự kiện.
        """
        if not raw_summary or not isinstance(raw_summary, dict):
            logger.warning("Invalid raw_summary data provided.")
            return None

        try:
            # Merge data
            merged_data = copy.deepcopy(raw_summary)
            if raw_detail and isinstance(raw_detail, dict):
                merged_data = deep_merge_dicts(merged_data, raw_detail)

            # Apply mapping rules
            flat_data = self._apply_mapping_rules(merged_data)
            
            # Validate required fields
            self._validate_required_fields(flat_data)

            # Extract and validate core data
            raw_status_desc = get_nested_value(merged_data, 'status.description')
            status = get_match_status(raw_status_desc, self.api_type) or MatchStatus.UNKNOWN
            
            raw_outcome_code = get_nested_value(merged_data, 'winnerCode') 
            outcome = get_match_outcome(raw_outcome_code, self.api_type) or MatchOutcome.UNKNOWN
            
            # Normalize team names
            home_team_name = MatchBusinessLogic.normalize_team_name(flat_data.get('home_team_name'))
            away_team_name = MatchBusinessLogic.normalize_team_name(flat_data.get('away_team_name'))
            
            if not home_team_name or not away_team_name:
                raise ValueError("Normalized team names cannot be empty.")

            # Business logic calculations
            importance = MatchBusinessLogic.determine_match_importance(home_team_name, away_team_name).value
            status_label = encode_match_status(status)
            outcome_label = MLOutcomeLabels.from_outcome(outcome)
            
            # League and season processing
            league_name = flat_data.get('league_name')
            league_country = flat_data.get('league_country')
            if not league_name or not league_country:
                raise ValueError("League name or country is missing.")
            
            parsed_league = ParsedLeague(name=league_name, country=league_country)
            
            season_name_from_api = flat_data.get('season_name') or flat_data.get('season_year_str')
            start_year = SeasonBusinessLogic.extract_year_from_season(season_name_from_api)
            if start_year is None:
                raise ValueError(f"Cannot determine season year from data: {season_name_from_api}")

            end_year = start_year + 1
            parsed_season = ParsedSeason(
                name=f"{start_year}/{str(end_year)[-2:]}", 
                start_year=start_year, 
                end_year=end_year, 
                league=parsed_league
            )
            
            # Stadium processing
            stadium = None
            if flat_data.get('venue_name'):
                stadium = ParsedStadium(
                    name=flat_data.get('venue_name'),
                    city=flat_data.get('venue_city'),
                    capacity=flat_data.get('venue_capacity'),
                    timezone=flat_data.get('venue_timezone') 
                )
            
            # Team processing
            home_team = ParsedTeam(
                external_id=self._safe_int_conversion(flat_data['home_team_id']), 
                name=home_team_name,
                short_name=get_nested_value(merged_data, 'homeTeam.shortName'),
                logo_url=f"https://api.sofascore.com/api/v1/team/{flat_data['home_team_id']}/image",
                stadium=stadium
            )
            
            away_team = ParsedTeam(
                external_id=self._safe_int_conversion(flat_data['away_team_id']), 
                name=away_team_name,
                short_name=get_nested_value(merged_data, 'awayTeam.shortName'),
                logo_url=f"https://api.sofascore.com/api/v1/team/{flat_data['away_team_id']}/image"
            )
            
            # Referee processing
            referee = None
            raw_referee_id = flat_data.get('referee_id')
            if raw_referee_id:
                referee_id = self._safe_int_conversion(raw_referee_id)
                referee_name = flat_data.get('referee_name')
                if referee_id and referee_name:
                    referee = ParsedReferee(external_id=referee_id, name=referee_name)

            # Create ParsedMatch object
            match = ParsedMatch(
                external_id=self._safe_int_conversion(flat_data['match_id']),
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
            
            # Validate critical fields
            if not match.match_datetime:
                raise ValueError("Match datetime is missing after transformation.")
            if not match.external_id:
                raise ValueError("Match external_id is missing after transformation.")

            # Transform events if provided
            if raw_events:
                # Create fresh cache for each match to avoid memory leaks
                player_cache: Dict[int, ParsedPlayer] = {}
                transformed_events = self._transform_single_match_events(
                    raw_events, match.home_team, match.away_team, player_cache
                )
                match.events = transformed_events
                # Clear cache after use
                player_cache.clear()
            
            if match.status == MatchStatus.UNKNOWN:
                logger.warning(f"Match {match.external_id} has an UNKNOWN status and will be skipped.")
                return None

            logger.info(f"Successfully transformed match {match.external_id} with {len(match.events)} events.")
            return match

        except ValueError as e:
            logger.error(f"Validation error transforming match: {e}", extra={"raw_summary_keys": list(raw_summary.keys())})
            return None
        except KeyError as e:
            logger.error(f"Missing key error transforming match: {e}", extra={"raw_summary_keys": list(raw_summary.keys())})
            return None
        except Exception as e:
            logger.error(f"Unexpected error transforming match: {e}", exc_info=True, extra={"raw_summary_keys": list(raw_summary.keys())})
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
        home_team: ParsedTeam, 
        away_team: ParsedTeam, 
        player_cache: Dict[int, ParsedPlayer]
    ) -> List[ParsedMatchEvent]:
        """
        Private helper: Biến đổi một danh sách các sự kiện thô cho một trận đấu.
        """
        if not raw_events_data:
            return []
        
        parsed_events = []
        
        for i, event in enumerate(raw_events_data):
            try:
                # Extract player information
                player = self._get_or_create_player_from_cache(
                    get_nested_value(event, 'player'), player_cache
                )
                related_player = self._get_or_create_player_from_cache(
                    get_nested_value(event, 'playerOut'), player_cache
                )
                
                # Normalize using unified mappers
                db_event_type = unified_event_type_mapper(get_nested_value(event, 'type'), self.api_type)
                db_period = unified_period_mapper(get_nested_value(event, 'period'), self.api_type)

                if not db_event_type or not db_period:
                    logger.debug(f"Skipping event {i}: invalid event_type or period")
                    continue
                
                # Determine event team
                team_side_str = get_nested_value(event, 'teamSide')
                event_team = None
                if team_side_str == 'home':
                    event_team = home_team
                elif team_side_str == 'away':
                    event_team = away_team
                else:
                    logger.warning(f"Unknown team side '{team_side_str}' for event {i}")

                # Create ParsedMatchEvent
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
                logger.error(f"Failed to transform event {i}: {e}", exc_info=True, extra={"event_data": event})
                continue  # Continue processing other events
        
        logger.debug(f"Transformed {len(parsed_events)}/{len(raw_events_data)} events successfully")
        return parsed_events