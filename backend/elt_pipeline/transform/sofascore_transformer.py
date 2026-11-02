# backend\elt_pipeline\transform\sofascore_transformer.py

import logging
from typing import Dict, Any, Optional, List, Tuple

# --- Import các cấu trúc dữ liệu và hằng số đã được chuẩn hóa ---
from .data_structures import (
    ParsedMatchBundle, ParsedMatch, ParsedLeague, ParsedSeason, ParsedTeam, 
    ParsedStadium, ParsedReferee, ParsedPlayer, ParsedMatchEvent, ParsedLineup, 
    ParsedSquadAvailability, ParsedMatchPlayerStats, ParsedMatchTeamStats
)
from config.core_constants import (
    get_match_status_from_sofascore, get_player_position_from_sofascore, 
    get_match_outcome_from_sofascore, get_player_availability_from_sofascore, 
    get_event_type_from_sofascore, MatchPeriod, MatchEventType, MatchOutcome
)
from config.business_constants import (
    team_name_normalizer, SeasonBusinessLogic, MatchBusinessLogic
)
from config.field_mappings import (
    convert_timestamp_to_utc_datetime, convert_timestamp_to_date, 
    convert_possession_to_decimal
)

logger = logging.getLogger(__name__)

class SofaScoreTransformer:
    """
    Lớp trung tâm của giai đoạn Transform trong pipeline.
    Nhiệm vụ chính: chuyển đổi dữ liệu raw JSON của một trận đấu từ SofaScore
    sang dạng cấu trúc chuẩn hóa (ParsedMatchBundle) để có thể nạp vào DB hoặc làm feature.

    Vì dữ liệu từ API thường không đồng nhất, lồng nhiều cấp, có thể thiếu field nên mọi xử lý
    trong lớp này phải an toàn, rõ ràng, log lỗi khi cần.
    """

    def __init__(self):
        """Lớp này không lưu trạng thái (stateless) - mỗi lần dùng để transform 1 trận."""
        pass

    @staticmethod
    def _get_nested_value(data: Dict, path: str, default: Any = None) -> Any:
        """
        Hàm tiện ích rất quan trọng - giúp lấy dữ liệu trong dict lồng nhau bằng path dạng 'a.b.c'.
        Trả về giá trị nếu tồn tại, nếu không thì trả về mặc định (default).
        Mục đích: API SofaScore thường có dữ liệu sâu nhiều tầng và thiếu key.
        Nếu không có hàm này, việc truy xuất sẽ dễ gây lỗi KeyError.      
        Ví dụ path: 'roundInfo.round'
        """
        keys = path.split('.')
        value = data
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value.get(key)
        return value

    def _transform_player(self, player_data: Optional[Dict]) -> Optional[ParsedPlayer]:
        """
        Chuyển đổi dữ liệu một cầu thủ thành ParsedPlayer.
        Vai trò: chuẩn hóa thông tin cầu thủ cho tất cả các tình huống: trong đội hình, ghi bàn, kiến tạo, vắng mặt, v.v.

        Trả về None nếu thiếu 'id' hoặc player_data không tồn tại.
        """
        if not player_data or not player_data.get('id'):
            return None
        
        return ParsedPlayer(
            external_id=player_data.get('id'),
            name=player_data.get('name'),
            position=get_player_position_from_sofascore(player_data.get('position')),
            date_of_birth=convert_timestamp_to_date(self._get_nested_value(player_data, 'dateOfBirthTimestamp')),
            nationality=self._get_nested_value(player_data, 'country.name'),
            height=player_data.get('height')
        )

    def _transform_team(self, team_data: Optional[Dict]) -> Optional[ParsedTeam]:
        """
        Chuyển dữ liệu một đội bóng thành ParsedTeam.
        Vai trò: cung cấp thông tin nhận diện đội để dùng trong cả match, events, lineups,...

        Bao gồm các thông tin như tên chuẩn hóa, tên ngắn, logo, HLV, màu áo.
        """
        if not team_data or not team_data.get('id'):
            return None
        
        team_id = team_data.get('id')
        return ParsedTeam(
            external_id=team_id,
            name=team_name_normalizer.normalize(team_data.get('name')),
            short_name=team_data.get('shortName'),
            logo_url=f"https://api.sofascore.com/api/v1/team/{team_id}/image",
            name_code=team_data.get('nameCode'),
            full_name=team_data.get('fullName'),
            fan_count=team_data.get('userCount'),
            manager_name=self._get_nested_value(team_data, 'manager.name'),
            manager_id=self._get_nested_value(team_data, 'manager.id'),
            primary_color=self._get_nested_value(team_data, 'teamColors.primary'),
            secondary_color=self._get_nested_value(team_data, 'teamColors.secondary')
        )

    def _transform_stadium(self, venue_data: Optional[Dict]) -> Optional[ParsedStadium]:
        """
        Chuyển thông tin venue/sân đấu thành ParsedStadium.
        Bao gồm: tên sân, thành phố, sức chứa, tọa độ GPS (nếu có).
        Vai trò: dùng để enrich thông tin trận đấu trong ParsedMatch.
        """
        if not venue_data or not venue_data.get('id'):
            return None
            
        return ParsedStadium(
            external_id=venue_data.get('id'),
            name=venue_data.get('name'),
            city=self._get_nested_value(venue_data, 'city.name'),
            capacity=self._get_nested_value(venue_data, 'stadium.capacity'),
            latitude=self._get_nested_value(venue_data, 'venueCoordinates.latitude'),
            longitude=self._get_nested_value(venue_data, 'venueCoordinates.longitude')
        )

    def _transform_referee(self, referee_data: Optional[Dict]) -> Optional[ParsedReferee]:
        """
        Chuyển dữ liệu trọng tài thành ParsedReferee.
        Vai trò: lưu thông tin trọng tài cầm còi trận, hỗ trợ phân tích bias, thẻ phạt,...
        """
        if not referee_data or not referee_data.get('id'):
            return None
            
        return ParsedReferee(
            external_id=referee_data.get('id'),
            name=referee_data.get('name'),
            country=self._get_nested_value(referee_data, 'country.name'),
            total_yellow_cards=referee_data.get('yellowCards'),
            total_red_cards=referee_data.get('redCards'),
            total_games_officiated=referee_data.get('games')
        )

    def _transform_league_and_season(self, match_data: Dict) -> Tuple[Optional[ParsedLeague], Optional[ParsedSeason]]:
        """
        Trích xuất và chuẩn hóa thông tin giải đấu và mùa giải từ raw match data.
        - Giải đấu (ParsedLeague): gồm tên, quốc gia, ID từ SofaScore.
        - Mùa giải (ParsedSeason): sử dụng logic nội bộ để tách năm từ chuỗi (ví dụ: "2023") nhằm tạo định danh mùa: 2023/2024.

        Trả về bộ tuple: (league, season). Nếu thiếu season, vẫn có thể trả về league.
        """
        tournament_data = match_data.get('tournament')
        season_data = match_data.get('season')

        if not tournament_data or not season_data:
            return None, None

        league = ParsedLeague(
            external_id=self._get_nested_value(tournament_data, 'uniqueTournament.id', tournament_data.get('id')),
            name=self._get_nested_value(tournament_data, 'uniqueTournament.name', tournament_data.get('name')),
            country=self._get_nested_value(tournament_data, 'category.name')
        )

        season_year_str = season_data.get('year')
        start_year = SeasonBusinessLogic.extract_year_from_season(season_year_str)
        if start_year is None:
            logger.warning(f"Không thể trích xuất năm từ mùa giải '{season_year_str}'.")
            return league, None
            
        season = ParsedSeason(
            external_id=season_data.get('id'),
            name=f"{start_year}/{start_year + 1}",
            start_year=start_year,
            end_year=start_year + 1,
            league=league
        )
        return league, season

    def _get_match_period(self, event_time: Optional[int], injury_times: Dict) -> MatchPeriod:
        """
        Xác định giai đoạn (hiệp đấu) của một sự kiện dựa trên phút xảy ra và thời gian bù giờ từng hiệp.
        Đây là logic quan trọng giúp xác định event diễn ra ở First Half, Second Half hay Extra Time.
        """
        if event_time is None: return MatchPeriod.FIRST_HALF # Mặc định an toàn
        
        it1 = injury_times.get('injuryTime1', 0)
        it2 = injury_times.get('injuryTime2', 0)
        
        if event_time <= 45 + it1: return MatchPeriod.FIRST_HALF
        if event_time <= 90 + it2: return MatchPeriod.SECOND_HALF
        if event_time <= 105: return MatchPeriod.EXTRA_TIME_1
        if event_time <= 120: return MatchPeriod.EXTRA_TIME_2
        return MatchPeriod.PENALTIES

    def _transform_events(self, events_data: List[Dict], team_map: Dict[int, ParsedTeam], player_id_to_team_map: Dict[int, int], home_team_id: int, away_team_id: int) -> List[ParsedMatchEvent]:
        """
        Chuyển danh sách các sự kiện trận đấu thành dạng chuẩn ParsedMatchEvent.
        Logic xác định đội của sự kiện được ưu tiên dựa trên cầu thủ, sau đó mới đến cờ isHome.
        Logic xác định hiệp đấu được làm lại để đáng tin cậy hơn.
        """
        parsed_events = []
        if not events_data: return []
        
        period_markers = sorted([e for e in events_data if e.get('incidentType') == 'period'], key=lambda x: x.get('time', 0))
        current_period = MatchPeriod.FIRST_HALF

        event_idx = 0
        marker_idx = 0

        while event_idx < len(events_data):
            event = events_data[event_idx]
            
            # Cập nhật hiệp đấu khi gặp dấu mốc tiếp theo
            if marker_idx < len(period_markers) and event.get('time', 0) >= period_markers[marker_idx].get('time', 0):
                text = period_markers[marker_idx].get('text', '').upper()
                if 'HT' in text or '1' in text: current_period = MatchPeriod.FIRST_HALF
                elif 'FT' in text or '2' in text: current_period = MatchPeriod.SECOND_HALF
                # Bổ sung logic cho hiệp phụ nếu cần
                marker_idx += 1
            
            incident_type = event.get('incidentType')
            if incident_type == 'period' or not incident_type:
                event_idx += 1
                continue
            
            if event.get('incidentClass') == 'ownGoal':
                event['incidentType'] = 'ownGoal' # Ghi đè để mapping nhận diện
            
            event_type = get_event_type_from_sofascore(event)
            if not event_type:
                event_idx += 1
                continue

            player_in_event = event.get('player', {})
            player_id = player_in_event.get('id')
            team = None
            
            # Ưu tiên 1: Dựa vào đội của cầu thủ
            if player_id and player_id in player_id_to_team_map:
                team_id = player_id_to_team_map[player_id]
                team = team_map.get(team_id)
            # Ưu tiên 2 (dự phòng): Dựa vào cờ isHome
            elif event.get('isHome') is True:
                team = team_map.get(home_team_id)
            elif event.get('isHome') is False:
                team = team_map.get(away_team_id)
            
            # Xử lý đặc biệt cho Own Goal: đội được hưởng lợi là đội đối phương
            if event_type == MatchEventType.OWN_GOAL and team:
                if team.external_id == home_team_id:
                    team = team_map.get(away_team_id)
                else:
                    team = team_map.get(home_team_id)

            player, related_player = None, None
            if event_type == MatchEventType.SUBSTITUTION:
                player = self._transform_player(event.get('playerOut'))
                related_player = self._transform_player(event.get('playerIn'))
            elif event_type in (MatchEventType.GOAL, MatchEventType.PENALTY_GOAL, MatchEventType.OWN_GOAL):
                player = self._transform_player(event.get('player'))
                related_player = self._transform_player(event.get('assist1'))
            else:
                player = self._transform_player(event.get('player'))

            parsed_events.append(
                ParsedMatchEvent(
                    minute=event.get('time'),
                    event_type=event_type,
                    team=team,
                    player=player,
                    related_player=related_player,
                    period=current_period,
                    raw_event_data=event
                )
            )
            event_idx += 1
        return parsed_events

    def _transform_lineups_and_player_stats(
        self, lineups_data: Optional[Dict], teams_by_side: Dict[str, ParsedTeam]
    ) -> Tuple[List[ParsedLineup], List[ParsedMatchPlayerStats], Dict[int, int]]:
        """
        Trích xuất thông tin đội hình ra sân và thống kê chi tiết từng cầu thủ trong trận đấu.
        Kết quả trả về là 2 danh sách:
        - ParsedLineup: danh sách đội hình chính và dự bị (vị trí, số áo, đội, v.v.)
        - ParsedMatchPlayerStats: thống kê như bàn thắng, chuyền, cản phá,...
        """
        parsed_lineups, parsed_player_stats = [], []
        player_id_to_team_map = {}
        if not lineups_data: return [], [], {}

        for team_side in ['home', 'away']:
            player_list = self._get_nested_value(lineups_data, f"{team_side}.players", [])
            if not player_list: continue

            team = teams_by_side[team_side]

            for player_entry in player_list:
                player = self._transform_player(player_entry.get('player'))
                if not player or not team: continue
                
                player_id_to_team_map[player.external_id] = team.external_id
                
                is_starter = not player_entry.get('substitute', False) # Mặc định là đá chính nếu không có key
                
                parsed_lineups.append(ParsedLineup(
                    player=player, team=team, is_starter=is_starter,
                    shirt_number=player_entry.get('shirtNumber'),
                    is_captain=player_entry.get('captain', False),
                    position_in_lineup=self._get_nested_value(player_entry, 'player.position')
                ))

                stats = player_entry.get('statistics', {})
                if 'minutesPlayed' in stats: # Chỉ xử lý cầu thủ có thống kê
                    parsed_player_stats.append(ParsedMatchPlayerStats(
                        player=player, team=team, is_starter=is_starter,
                        minutes_played=stats.get('minutesPlayed', 0),
                        goals=stats.get('goals', 0),
                        assists=stats.get('goalAssist', 0),
                        shots=stats.get('totalScoringAttempt', 0) or stats.get('shots',0),
                        shots_on_target=stats.get('onTargetScoringAttempt', 0) or stats.get('shotsOnTarget',0),
                        passes=stats.get('totalPass', 0),
                        accurate_passes=stats.get('accuratePass', 0),
                        key_passes=stats.get('keyPass', 0),
                        tackles=stats.get('totalTackle', 0),
                        interceptions=stats.get('interceptionWon', 0),
                        fouls_committed=stats.get('fouls', 0),
                        fouls_drawn=stats.get('wasFouled', 0),
                        saves=stats.get('saves', 0)
                    ))
        return parsed_lineups, parsed_player_stats, player_id_to_team_map

    def _transform_squad_availability(self, lineups_data: Optional[Dict], teams_by_side: Dict[str, ParsedTeam]) -> List[ParsedSquadAvailability]:
        """
        Chuyển đổi thông tin cầu thủ vắng mặt (do chấn thương, treo giò,...).
        Trích xuất từ trường 'missingPlayers' của lineups.
        """
        parsed_availabilities = []
        if not lineups_data: return []

        for team_side in ['home', 'away']:
            missing_list = self._get_nested_value(lineups_data, f"{team_side}.missingPlayers", [])
            if not missing_list: continue

            team = teams_by_side[team_side]

            for missing_entry in missing_list:
                player = self._transform_player(missing_entry.get('player'))
                status_str = "missing" if missing_entry.get('type') == 'missing' else missing_entry.get('reason')
                status = get_player_availability_from_sofascore(status_str)
                if player and status and team:
                    parsed_availabilities.append(ParsedSquadAvailability(
                        player=player, team=team, status=status,
                        notes=f"Type: {missing_entry.get('type')}, Reason: {missing_entry.get('reason')}"
                    ))
        return parsed_availabilities

    def _transform_team_stats(self, stats_data: Optional[Dict], home_team: ParsedTeam, away_team: ParsedTeam) -> List[ParsedMatchTeamStats]:
        """
        Trích xuất thống kê toàn đội của cả hai đội trong toàn bộ trận.
        Sử dụng group có period='ALL'.
        """
        if not all([stats_data, home_team, away_team]): return []

        all_periods_stats = next((p for p in stats_data.get('statistics', []) if p.get('period') == 'ALL'), None)
        if not all_periods_stats: 
            logger.warning("Không tìm thấy thống kê với period='ALL'.")
            return []

        home_values, away_values = {}, {}
        for group in all_periods_stats.get('groups', []):
            for item in group.get('statisticsItems', []):
                key = item.get('key')
                if key:
                    # ### FIXED ###: Lấy đúng giá trị từ `home` và `away` thay vì `homeValue`, `awayValue`
                    home_values[key] = item.get('home')
                    away_values[key] = item.get('away')
        
        home_team_stats = ParsedMatchTeamStats(
            team=home_team,
            possession_percentage=convert_possession_to_decimal(home_values.get('ballPossession')),
            total_shots=int(home_values.get('totalShotsOnGoal', 0)),
            shots_on_target=int(home_values.get('shotsOnGoal', 0)),
            shots_off_target=int(home_values.get('shotsOffGoal', 0)),
            blocked_shots=int(home_values.get('blockedScoringAttempt', 0)),
            fouls_committed=int(home_values.get('fouls', 0)),
            corners=int(home_values.get('cornerKicks', 0)),
            offsides=int(home_values.get('offsides', 0)),
            saves=int(home_values.get('goalkeeperSaves', 0))
        )
        away_team_stats = ParsedMatchTeamStats(
            team=away_team,
            possession_percentage=convert_possession_to_decimal(away_values.get('ballPossession')),
            total_shots=int(away_values.get('totalShotsOnGoal', 0)),
            shots_on_target=int(away_values.get('shotsOnGoal', 0)),
            shots_off_target=int(away_values.get('shotsOffGoal', 0)),
            blocked_shots=int(away_values.get('blockedScoringAttempt', 0)),
            fouls_committed=int(away_values.get('fouls', 0)),
            corners=int(away_values.get('cornerKicks', 0)),
            offsides=int(away_values.get('offsides', 0)),
            saves=int(away_values.get('goalkeeperSaves', 0))
        )
        return [home_team_stats, away_team_stats]

    def transform_match_bundle(
        self, raw_bundle_data: Dict
    ) -> Optional[ParsedMatchBundle]:
        """
        Hàm entry-point chính của transformer.
        Nó nhận toàn bộ bundle JSON gốc và tự trích xuất các phần cần thiết.
        """
        ### FIXED ###: Tự trích xuất dữ liệu từ bundle gốc.
        details = raw_bundle_data.get('details', {})
        incidents = raw_bundle_data.get('incidents', {})
        lineups = raw_bundle_data.get('lineups', {})
        statistics = raw_bundle_data.get('statistics', {})

        raw_match_data = details.get("event")
        if not raw_match_data or 'id' not in raw_match_data:
            logger.error("Dữ liệu 'details.event' không hợp lệ. Không thể transform.")
            return None

        _, season = self._transform_league_and_season(raw_match_data)
        stadium = self._transform_stadium(raw_match_data.get('venue'))
        referee = self._transform_referee(raw_match_data.get('referee'))
        home_team = self._transform_team(raw_match_data.get('homeTeam'))
        away_team = self._transform_team(raw_match_data.get('awayTeam'))

        if not all([season, home_team, away_team]):
            logger.error("Thiếu dữ liệu Season, HomeTeam hoặc AwayTeam. Không thể tạo trận đấu.")
            return None
        
        team_map = {home_team.external_id: home_team, away_team.external_id: away_team}
        teams_by_side = {"home": home_team, "away": away_team}

        # Ưu tiên 'normaltime', nếu không có thì dùng 'current'
        home_goals = self._get_nested_value(raw_match_data, 'homeScore.normaltime')
        away_goals = self._get_nested_value(raw_match_data, 'awayScore.normaltime')
        if home_goals is None: home_goals = self._get_nested_value(raw_match_data, 'homeScore.current')
        if away_goals is None: away_goals = self._get_nested_value(raw_match_data, 'awayScore.current')

        ### FIXED ###: Lấy tỷ số hiệp 1 một cách đáng tin cậy
        ht_score_event = next((e for e in self._get_nested_value(incidents, 'incidents', []) if e.get('incidentType') == 'period' and e.get('text', '').upper() == 'HT'), None)
        if ht_score_event:
            half_time_home_goals = ht_score_event.get('homeScore')
            half_time_away_goals = ht_score_event.get('awayScore')
        else: # Dự phòng nếu không có sự kiện HT
            half_time_home_goals = self._get_nested_value(raw_match_data, 'homeScore.period1')
            half_time_away_goals = self._get_nested_value(raw_match_data, 'awayScore.period1')
        
        status = get_match_status_from_sofascore(self._get_nested_value(raw_match_data, 'status.type'))
        if status is None:
            logger.error("Match %s has an unsupported status.", raw_match_data['id'])
            return None
        match_datetime = convert_timestamp_to_utc_datetime(raw_match_data.get('startTimestamp'))
        if match_datetime is None:
            logger.error("Match %s has no valid kickoff timestamp.", raw_match_data['id'])
            return None
        if status.value == 'FINISHED' and (home_goals is None or away_goals is None):
            logger.error("Finished match %s has no final score.", raw_match_data['id'])
            return None
        final_outcome = (
            MatchBusinessLogic.determine_outcome_from_score(home_goals, away_goals)
            if status.value == 'FINISHED' else None
        )
        round_number = self._get_nested_value(raw_match_data, 'roundInfo.round')

        match = ParsedMatch(
            external_id=raw_match_data['id'],
            season=season,
            match_datetime=match_datetime,
            match_week=str(round_number) if round_number is not None else None,
            home_team=home_team,
            away_team=away_team,
            stadium=stadium,
            referee=referee,
            status=status,
            outcome=final_outcome,
            home_goals=home_goals,
            away_goals=away_goals,
            half_time_home_goals=half_time_home_goals,
            half_time_away_goals=half_time_away_goals,
            attendance=raw_match_data.get('attendance')
        )
        
        ### FIXED ###: Sửa đổi luồng xử lý để tạo map player-team trước
        lineups_list, player_stats_list, player_id_to_team_map = self._transform_lineups_and_player_stats(lineups, teams_by_side)
        
        events = self._transform_events(
            self._get_nested_value(incidents, 'incidents', []), team_map,
            player_id_to_team_map, home_team.external_id, away_team.external_id
        )
        
        squad_availability_list = self._transform_squad_availability(lineups, teams_by_side)
        team_stats_list = self._transform_team_stats(statistics, home_team, away_team)

        return ParsedMatchBundle(
            match=match,
            events=events,
            lineups=lineups_list,
            squad_availability=squad_availability_list,
            player_stats=player_stats_list,
            team_stats=team_stats_list
        )
