# ai-engine\elt_pipeline\transform\sofascore_transformer.py

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
    get_event_type_from_sofascore, MatchPeriod, MatchEventType
)
from config.business_constants import (
    team_name_normalizer, SeasonBusinessLogic
)
from config.field_mappings import (
    convert_timestamp_to_utc_datetime, convert_timestamp_to_date, 
    convert_possession_to_decimal
)

logger = logging.getLogger(__name__)

class SofaScoreTransformer:
    """
    Chuyển đổi dữ liệu thô từ SofaScore API thành các đối tượng ParsedMatchBundle có cấu trúc.
    Lớp này được thiết kế để xử lý toàn bộ "bundle" dữ liệu của một trận đấu.
    """

    def __init__(self):
        """Khởi tạo Transformer. Lớp này không có trạng thái (stateless)."""
        pass

    @staticmethod
    def _get_nested_value(data: Dict, path: str, default: Any = None) -> Any:
        """
        Lấy giá trị từ một dictionary lồng nhau một cách an toàn.
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
        """Chuyển đổi dữ liệu thô của một cầu thủ thành đối tượng ParsedPlayer."""
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
        """Chuyển đổi dữ liệu thô của một đội bóng thành đối tượng ParsedTeam."""
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
        """Chuyển đổi dữ liệu thô của sân vận động thành đối tượng ParsedStadium."""
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
        """Chuyển đổi dữ liệu thô của trọng tài thành đối tượng ParsedReferee."""
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
        """Chuyển đổi dữ liệu giải đấu và mùa giải từ dữ liệu trận đấu."""
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
        """Xác định hiệp đấu từ thời gian của sự kiện và thời gian bù giờ."""
        if event_time is None: return MatchPeriod.FIRST_HALF # Mặc định an toàn
        
        it1 = injury_times.get('injuryTime1', 0)
        it2 = injury_times.get('injuryTime2', 0)
        
        if event_time <= 45 + it1: return MatchPeriod.FIRST_HALF
        if event_time <= 90 + it2: return MatchPeriod.SECOND_HALF
        if event_time <= 105: return MatchPeriod.EXTRA_TIME_1
        if event_time <= 120: return MatchPeriod.EXTRA_TIME_2
        return MatchPeriod.PENALTIES

    def _transform_events(self, events_data: List[Dict], team_map: Dict[int, ParsedTeam], injury_time_data: Dict, home_team_id: int, away_team_id: int) -> List[ParsedMatchEvent]:
        """Chuyển đổi danh sách sự kiện thô."""
        parsed_events = []
        if not events_data: return []

        for event in events_data:
            incident_type = event.get('incidentType')
            if incident_type == 'period' or not incident_type: continue
            
            event_type = get_event_type_from_sofascore(event)
            if not event_type: continue

            team = None
            if event.get('isHome') is True: team = team_map.get(home_team_id)
            elif event.get('isHome') is False: team = team_map.get(away_team_id)

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
                    period=self._get_match_period(event.get('time'), injury_time_data),
                    raw_event_data=event
                )
            )
        return parsed_events

    def _transform_lineups_and_player_stats(
        self, lineups_data: Optional[Dict], team_map: Dict[int, ParsedTeam]
    ) -> Tuple[List[ParsedLineup], List[ParsedMatchPlayerStats]]:
        """Chuyển đổi đội hình và thống kê cầu thủ từ cùng một nguồn dữ liệu."""
        parsed_lineups, parsed_player_stats = [], []
        if not lineups_data: return [], []

        for team_side in ['home', 'away']:
            player_list = self._get_nested_value(lineups_data, f"{team_side}.players", [])
            team_id = self._get_nested_value(player_list, '0.teamId')
            team = team_map.get(team_id) if team_id else None

            for player_entry in player_list:
                player = self._transform_player(player_entry.get('player'))
                if not player or not team: continue
                
                is_starter = not player_entry.get('substitute', True)
                
                parsed_lineups.append(ParsedLineup(
                    player=player, team=team, is_starter=is_starter,
                    shirt_number=player_entry.get('shirtNumber'),
                    is_captain=player_entry.get('captain', False),
                    position_in_lineup=player_entry.get('position')
                ))

                stats = player_entry.get('statistics', {})
                if 'minutesPlayed' in stats:
                    parsed_player_stats.append(ParsedMatchPlayerStats(
                        player=player, team=team, is_starter=is_starter,
                        minutes_played=stats.get('minutesPlayed', 0),
                        goals=stats.get('goals', 0),
                        assists=stats.get('goalAssist', 0),
                        shots=stats.get('totalScoringAttempt', 0),
                        shots_on_target=stats.get('onTargetScoringAttempt', 0),
                        passes=stats.get('totalPass', 0),
                        accurate_passes=stats.get('accuratePass', 0),
                        key_passes=stats.get('keyPass', 0),
                        tackles=stats.get('totalTackle', 0),
                        interceptions=stats.get('interceptionWon', 0),
                        fouls_committed=stats.get('fouls', 0),
                        fouls_drawn=stats.get('wasFouled', 0),
                        saves=stats.get('saves', 0)
                    ))
        return parsed_lineups, parsed_player_stats

    def _transform_squad_availability(self, lineups_data: Optional[Dict], team_map: Dict[int, ParsedTeam]) -> List[ParsedSquadAvailability]:
        """Chuyển đổi thông tin cầu thủ vắng mặt."""
        parsed_availabilities = []
        if not lineups_data: return []

        for team_side in ['home', 'away']:
            missing_list = self._get_nested_value(lineups_data, f"{team_side}.missingPlayers", [])
            team_id = self._get_nested_value(lineups_data, f"{team_side}.players.0.teamId")
            team = team_map.get(team_id) if team_id else None

            for missing_entry in missing_list:
                player = self._transform_player(missing_entry.get('player'))
                status = get_player_availability_from_sofascore(missing_entry.get('type'))
                if player and status and team:
                    parsed_availabilities.append(ParsedSquadAvailability(
                        player=player, team=team, status=status,
                        notes=f"Reason code: {missing_entry.get('reason')}"
                    ))
        return parsed_availabilities

    def _transform_team_stats(self, stats_data: Optional[Dict], home_team: ParsedTeam, away_team: ParsedTeam) -> List[ParsedMatchTeamStats]:
        """Chuyển đổi thống kê toàn trận của hai đội."""
        if not all([stats_data, home_team, away_team]): return []

        all_periods_stats = next((p for p in stats_data.get('statistics', []) if p.get('period') == 'ALL'), None)
        if not all_periods_stats: return []

        home_values, away_values = {}, {}
        for group in all_periods_stats.get('groups', []):
            for item in group.get('statisticsItems', []):
                key = item.get('key')
                if key:
                    home_values[key] = item.get('homeValue', item.get('home'))
                    away_values[key] = item.get('awayValue', item.get('away'))
        
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
        self, details: Dict, incidents: Optional[Dict], lineups: Optional[Dict], statistics: Optional[Dict]
    ) -> Optional[ParsedMatchBundle]:
        """
        Phương thức chính, nhận tất cả dữ liệu thô và trả về một ParsedMatchBundle hoàn chỉnh.
        """
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

        # SỬA LỖI TỶ SỐ: Ưu tiên 'normaltime', nếu không có thì dùng 'current'
        home_goals = self._get_nested_value(raw_match_data, 'homeScore.normaltime', self._get_nested_value(raw_match_data, 'homeScore.current'))
        away_goals = self._get_nested_value(raw_match_data, 'awayScore.normaltime', self._get_nested_value(raw_match_data, 'awayScore.current'))

        match = ParsedMatch(
            external_id=raw_match_data['id'],
            season=season,
            match_datetime=convert_timestamp_to_utc_datetime(raw_match_data.get('startTimestamp')),
            match_week=str(self._get_nested_value(raw_match_data, 'roundInfo.round')),
            home_team=home_team,
            away_team=away_team,
            stadium=stadium,
            referee=referee,
            status=get_match_status_from_sofascore(self._get_nested_value(raw_match_data, 'status.type')),
            outcome=get_match_outcome_from_sofascore(raw_match_data.get('winnerCode')),
            home_goals=home_goals,
            away_goals=away_goals,
            half_time_home_goals=self._get_nested_value(raw_match_data, 'homeScore.period1'),
            half_time_away_goals=self._get_nested_value(raw_match_data, 'awayScore.period1'),
            attendance=raw_match_data.get('attendance')
        )
        
        events = self._transform_events(
            self._get_nested_value(incidents, 'incidents', []), team_map,
            raw_match_data.get('time', {}), home_team.external_id, away_team.external_id
        )
        lineups_list, player_stats_list = self._transform_lineups_and_player_stats(lineups, team_map)
        squad_availability_list = self._transform_squad_availability(lineups, team_map)
        team_stats_list = self._transform_team_stats(statistics, home_team, away_team)

        return ParsedMatchBundle(
            match=match,
            events=events,
            lineups=lineups_list,
            squad_availability=squad_availability_list,
            player_stats=player_stats_list,
            team_stats=team_stats_list
        )