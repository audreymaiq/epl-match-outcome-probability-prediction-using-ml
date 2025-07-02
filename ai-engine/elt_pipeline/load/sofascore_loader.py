# elt_pipeline/load/sofascore_loader.py

"""
SofaScore ETL Pipeline: Loader 
"""

import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from contextlib import contextmanager

from elt_pipeline.transform.data_structures import (
    ParsedMatch, ParsedTeam, ParsedStadium, ParsedReferee, ParsedLeague, ParsedSeason, ParsedPlayer, ParsedMatchEvent
)
from config.core_constants import MatchStatus
from utils.external_mapping import get_internal_id, upsert_mapping

logger = logging.getLogger(__name__)

class LoaderError(Exception):
    """Custom exception for loader errors."""
    pass

class SofaScoreLoader:
    """
    Chịu trách nhiệm ghi các đối tượng đã chuẩn hóa vào DB.
    """

    def __init__(self, session: Session):
        self.session = session
        self._validate_session()
        self._entity_cache: Dict[str, int] = {}

    def _validate_session(self):
        """Kiểm tra session database."""
        if not self.session:
            raise ValueError("Database session is required")
        try:
            self.session.execute(text("SELECT 1"))
        except Exception as e:
            logger.error(f"Database session validation failed: {e}")
            raise LoaderError(f"Invalid database session: {e}")

    @contextmanager
    def _transaction_context(self):
        """Context manager cho database transactions."""
        # Nếu đã có transaction đang chạy, không tạo transaction mới
        if self.session.in_transaction():
            yield
            return
        
        try:
            with self.session.begin_nested():
                yield
        except Exception as e:
            # Rollback sẽ được xử lý bởi transaction cha nếu có
            logger.error(f"Transaction block failed: {e}")
            raise

    def _get_cache_key(self, entity_type: str, external_id: Any) -> str:
        """Tạo cache key nhất quán."""
        return f"{entity_type}:{external_id}"

    def _check_entity_cache(self, entity_type: str, external_id: Any) -> Optional[int]:
        """Kiểm tra entity có trong cache không."""
        if not external_id: return None
        return self._entity_cache.get(self._get_cache_key(entity_type, external_id))

    def _cache_entity(self, entity_type: str, external_id: Any, internal_id: int):
        """Cache entity để tra cứu sau này."""
        if not external_id: return
        self._entity_cache[self._get_cache_key(entity_type, external_id)] = internal_id

    def upsert_league(self, league: ParsedLeague) -> Optional[int]:
        """Upsert một giải đấu."""
        if not league or not league.external_id: return None
        
        try:
            if league.internal_id: return league.internal_id
            
            # Check cache and mapping
            cached_id = self._check_entity_cache("league", league.external_id)
            if cached_id: league.internal_id = cached_id; return cached_id
            
            internal_id = get_internal_id(str(league.external_id), "league", "sofascore", self.session)
            if internal_id: 
                self._cache_entity("league", league.external_id, internal_id)
                league.internal_id = internal_id
                return internal_id

            query = text("""
                INSERT INTO "Leagues" (name, country, unique_tournament_id, priority)
                VALUES (:name, :country, :unique_tournament_id, :priority)
                ON CONFLICT (name, country) DO UPDATE SET
                    unique_tournament_id = COALESCE(EXCLUDED.unique_tournament_id, "Leagues".unique_tournament_id),
                    priority = COALESCE(EXCLUDED.priority, "Leagues".priority),
                    updated_at = NOW()
                RETURNING id;
            """)
            params = {
                "name": league.name.strip(),
                "country": league.country.strip() if league.country else None,
                "unique_tournament_id": league.unique_tournament_id,
                "priority": league.priority
            }
            
            result = self.session.execute(text(query), params)
            league.internal_id = result.scalar_one_or_none()
            
            if league.internal_id:
                upsert_mapping(str(league.external_id), league.internal_id, "league", "sofascore", session=self.session)
                self._cache_entity("league", league.external_id, league.internal_id)
            
            return league.internal_id
            
        except Exception as e:
            logger.error(f"Error upserting league '{getattr(league, 'name', 'Unknown')}': {e}", exc_info=True)
            raise LoaderError(f"Failed to upsert league: {e}")

    def upsert_season(self, season: ParsedSeason) -> Optional[int]:
        """Upsert một mùa giải."""
        if not season or not season.external_id: return None
        
        try:
            if season.internal_id: return season.internal_id

            cached_id = self._check_entity_cache("season", season.external_id)
            if cached_id: season.internal_id = cached_id; return cached_id

            internal_id = get_internal_id(str(season.external_id), "season", "sofascore", self.session)
            if internal_id: 
                self._cache_entity("season", season.external_id, internal_id)
                season.internal_id = internal_id
                return internal_id

            league_id = self.upsert_league(season.league)
            if not league_id: raise LoaderError(f"Could not get ID for league: {season.league.name}")

            query = text("""
                INSERT INTO "Seasons" (league_id, start_year, end_year, name)
                VALUES (:league_id, :start_year, :end_year, :name)
                ON CONFLICT (league_id, name) DO UPDATE SET
                    start_year = EXCLUDED.start_year,
                    end_year = EXCLUDED.end_year,
                    updated_at = NOW()
                RETURNING id;
            """)
            params = {
                "league_id": league_id,
                "start_year": season.start_year,
                "end_year": season.end_year,
                "name": season.name.strip()
            }
            
            result = self.session.execute(text(query), params)
            season.internal_id = result.scalar_one_or_none()
            
            if season.internal_id:
                upsert_mapping(str(season.external_id), season.internal_id, "season", "sofascore", session=self.session)
                self._cache_entity("season", season.external_id, season.internal_id)
            
            return season.internal_id
            
        except Exception as e:
            logger.error(f"Error upserting season '{getattr(season, 'name', 'Unknown')}': {e}", exc_info=True)
            raise LoaderError(f"Failed to upsert season: {e}")

    def upsert_stadium(self, stadium: ParsedStadium) -> Optional[int]:
        """Upsert một sân vận động."""
        if not stadium or not stadium.external_id: return None
            
        try:
            if stadium.internal_id: return stadium.internal_id

            cached_id = self._check_entity_cache("stadium", stadium.external_id)
            if cached_id: stadium.internal_id = cached_id; return cached_id
            
            internal_id = get_internal_id(str(stadium.external_id), "stadium", "sofascore", self.session)
            if internal_id: 
                self._cache_entity("stadium", stadium.external_id, internal_id)
                stadium.internal_id = internal_id
                return internal_id

            query = text("""
                INSERT INTO "Stadiums" (name, city, capacity, latitude, longitude)
                VALUES (:name, :city, :capacity, :latitude, :longitude)
                ON CONFLICT (name, city) DO UPDATE SET
                    capacity = COALESCE(EXCLUDED.capacity, "Stadiums".capacity),
                    latitude = COALESCE(EXCLUDED.latitude, "Stadiums".latitude),
                    longitude = COALESCE(EXCLUDED.longitude, "Stadiums".longitude),
                    updated_at = NOW()
                RETURNING id;
            """)
            params = {
                "name": stadium.name.strip() if stadium.name else "Unknown",
                "city": stadium.city.strip() if stadium.city else None,
                "capacity": stadium.capacity,
                "latitude": stadium.latitude,
                "longitude": stadium.longitude
            }
            
            result = self.session.execute(text(query), params)
            stadium.internal_id = result.scalar_one_or_none()
            
            if stadium.internal_id:
                upsert_mapping(str(stadium.external_id), stadium.internal_id, "stadium", "sofascore", session=self.session)
                self._cache_entity("stadium", stadium.external_id, stadium.internal_id)
            
            return stadium.internal_id
            
        except Exception as e:
            logger.error(f"Error upserting stadium '{getattr(stadium, 'name', 'Unknown')}': {e}", exc_info=True)
            raise LoaderError(f"Failed to upsert stadium: {e}")

    def upsert_team(self, team: ParsedTeam) -> Optional[int]:
        """Upsert một đội bóng."""
        if not team or not team.external_id: return None
            
        try:
            if team.internal_id: return team.internal_id

            cached_id = self._check_entity_cache("team", team.external_id)
            if cached_id: team.internal_id = cached_id; return cached_id

            internal_id = get_internal_id(str(team.external_id), "team", "sofascore", self.session)
            if internal_id: 
                self._cache_entity("team", team.external_id, internal_id)
                team.internal_id = internal_id
                return internal_id

            stadium_id = self.upsert_stadium(team.stadium) if team.stadium else None

            query = text("""
                INSERT INTO "Teams" (
                    name, short_name, name_code, full_name, stadium_id, 
                    established_year, logo_url, fan_count, manager_name, 
                    manager_id, manager_country, primary_color, secondary_color
                )
                VALUES (
                    :name, :short_name, :name_code, :full_name, :stadium_id, 
                    :established_year, :logo_url, :fan_count, :manager_name, 
                    :manager_id, :manager_country, :primary_color, :secondary_color
                )
                ON CONFLICT (name) DO UPDATE SET
                    short_name = COALESCE(EXCLUDED.short_name, "Teams".short_name),
                    name_code = COALESCE(EXCLUDED.name_code, "Teams".name_code),
                    full_name = COALESCE(EXCLUDED.full_name, "Teams".full_name),
                    stadium_id = COALESCE(EXCLUDED.stadium_id, "Teams".stadium_id),
                    established_year = COALESCE(EXCLUDED.established_year, "Teams".established_year),
                    logo_url = COALESCE(EXCLUDED.logo_url, "Teams".logo_url),
                    fan_count = COALESCE(EXCLUDED.fan_count, "Teams".fan_count),
                    manager_name = COALESCE(EXCLUDED.manager_name, "Teams".manager_name),
                    manager_id = COALESCE(EXCLUDED.manager_id, "Teams".manager_id),
                    manager_country = COALESCE(EXCLUDED.manager_country, "Teams".manager_country),
                    primary_color = COALESCE(EXCLUDED.primary_color, "Teams".primary_color),
                    secondary_color = COALESCE(EXCLUDED.secondary_color, "Teams".secondary_color),
                    updated_at = NOW()
                RETURNING id;
            """)
            
            params = {
                "name": team.name.strip(),
                "short_name": team.short_name.strip() if team.short_name else None,
                "name_code": team.name_code,
                "full_name": team.full_name,
                "stadium_id": stadium_id,
                "established_year": team.established_year,
                "logo_url": team.logo_url,
                "fan_count": team.fan_count,
                "manager_name": team.manager_name,
                "manager_id": team.manager_id,
                "manager_country": team.manager_country,
                "primary_color": team.primary_color,
                "secondary_color": team.secondary_color
            }
            
            result = self.session.execute(query, params)
            team.internal_id = result.scalar_one_or_none()

            if team.internal_id:
                upsert_mapping(str(team.external_id), team.internal_id, "team", "sofascore", session=self.session)
                self._cache_entity("team", team.external_id, team.internal_id)
            
            return team.internal_id
            
        except Exception as e:
            logger.error(f"Error upserting team '{getattr(team, 'name', 'Unknown')}': {e}", exc_info=True)
            raise LoaderError(f"Failed to upsert team: {e}")

    def upsert_referee(self, referee: ParsedReferee) -> Optional[int]:
        """Upsert một trọng tài."""
        if not referee or not referee.external_id: return None
            
        try:
            if referee.internal_id: return referee.internal_id

            cached_id = self._check_entity_cache("referee", referee.external_id)
            if cached_id: referee.internal_id = cached_id; return cached_id

            internal_id = get_internal_id(str(referee.external_id), "referee", "sofascore", self.session)
            if internal_id: 
                self._cache_entity("referee", referee.external_id, internal_id)
                referee.internal_id = internal_id
                return internal_id

            query = text("""
                INSERT INTO "Referees" (
                    name, country, total_yellow_cards, total_red_cards, 
                    total_yellow_red_cards, total_games_officiated
                )
                VALUES (
                    :name, :country, :total_yellow_cards, :total_red_cards, 
                    :total_yellow_red_cards, :total_games_officiated
                )
                ON CONFLICT (name, country) DO UPDATE SET
                    total_yellow_cards = COALESCE(EXCLUDED.total_yellow_cards, "Referees".total_yellow_cards),
                    total_red_cards = COALESCE(EXCLUDED.total_red_cards, "Referees".total_red_cards),
                    total_yellow_red_cards = COALESCE(EXCLUDED.total_yellow_red_cards, "Referees".total_yellow_red_cards),
                    total_games_officiated = COALESCE(EXCLUDED.total_games_officiated, "Referees".total_games_officiated),
                    updated_at = NOW()
                RETURNING id;
            """)
            params = {
                "name": referee.name.strip(),
                "country": referee.country.strip() if referee.country else None,
                "total_yellow_cards": referee.total_yellow_cards,
                "total_red_cards": referee.total_red_cards,
                "total_yellow_red_cards": referee.total_yellow_red_cards,
                "total_games_officiated": referee.total_games_officiated
            }
            
            result = self.session.execute(text(query), params)
            referee.internal_id = result.scalar_one_or_none()

            if referee.internal_id:
                upsert_mapping(str(referee.external_id), referee.internal_id, "referee", "sofascore", session=self.session)
                self._cache_entity("referee", referee.external_id, referee.internal_id)
            
            return referee.internal_id
            
        except Exception as e:
            logger.error(f"Error upserting referee '{getattr(referee, 'name', 'Unknown')}': {e}", exc_info=True)
            raise LoaderError(f"Failed to upsert referee: {e}")

    def upsert_player(self, player: ParsedPlayer) -> Optional[int]:
        """Upsert một cầu thủ."""
        if not player or not player.external_id: return None
            
        try:
            if player.internal_id: return player.internal_id

            cached_id = self._check_entity_cache("player", player.external_id)
            if cached_id: player.internal_id = cached_id; return cached_id

            internal_id = get_internal_id(str(player.external_id), "player", "sofascore", self.session)
            if internal_id: 
                self._cache_entity("player", player.external_id, internal_id)
                player.internal_id = internal_id
                return internal_id

            query = text("""
                INSERT INTO "Players" (name, "position", date_of_birth, nationality)
                VALUES (:name, :position, :date_of_birth, :nationality)
                ON CONFLICT (name, date_of_birth) DO UPDATE SET
                    "position" = COALESCE(EXCLUDED."position", "Players"."position"),
                    nationality = COALESCE(EXCLUDED.nationality, "Players".nationality),
                    updated_at = NOW()
                RETURNING id;
            """)
            params = {
                "name": player.name.strip(),
                "position": player.position.value if player.position else None, # Sử dụng enum value
                "date_of_birth": player.date_of_birth,
                "nationality": player.nationality.strip() if player.nationality else None
            }
            
            result = self.session.execute(text(query), params)
            player.internal_id = result.scalar_one_or_none()

            if player.internal_id:
                upsert_mapping(str(player.external_id), player.internal_id, "player", "sofascore", session=self.session)
                self._cache_entity("player", player.external_id, player.internal_id)
            
            return player.internal_id
            
        except Exception as e:
            logger.error(f"Error upserting player '{getattr(player, 'name', 'Unknown')}': {e}", exc_info=True)
            raise LoaderError(f"Failed to upsert player: {e}")

    def upsert_match(self, match: ParsedMatch) -> Optional[int]:
        """Upsert một trận đấu."""
        try:
            if match.internal_id: return match.internal_id
            
            if match.external_id:
                internal_id = get_internal_id(str(match.external_id), "match", "sofascore", self.session)
                if internal_id: 
                    match.internal_id = internal_id
                    return internal_id

            if not all([match.home_team.internal_id, match.away_team.internal_id, match.season.internal_id]):
                raise LoaderError("Missing internal IDs for home_team, away_team, or season.")

            outcome_value = match.outcome.value if match.outcome and match.status == MatchStatus.FINISHED else None
            
            query = text('''
                INSERT INTO "Matches" (
                    season_id, match_datetime, match_week, home_team_id, away_team_id, 
                    stadium_id, referee_id, status, status_label, 
                    home_goals, away_goals, outcome, outcome_label, outcome_code,
                    half_time_home_goals, half_time_away_goals, 
                    second_half_home_goals, second_half_away_goals,
                    home_goals_normaltime, away_goals_normaltime,
                    injury_time_first_half, injury_time_second_half,
                    attendance, importance, has_xg, has_event_player_statistics
                )
                VALUES (
                    :season_id, :dt, :match_week, :h_id, :a_id, :st_id, :ref_id, :status, :status_label,
                    :hg, :ag, :outcome, :outcome_label, :outcome_code,
                    :hthg, :htag, :shhg, :shag, :hg_normal, :ag_normal,
                    :it1, :it2, :attendance, :importance, :has_xg, :has_events
                )
                ON CONFLICT (match_datetime, home_team_id, away_team_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    status_label = EXCLUDED.status_label,
                    home_goals = EXCLUDED.home_goals,
                    away_goals = EXCLUDED.away_goals,
                    outcome = EXCLUDED.outcome,
                    outcome_label = EXCLUDED.outcome_label,
                    outcome_code = EXCLUDED.outcome_code,
                    half_time_home_goals = EXCLUDED.half_time_home_goals,
                    half_time_away_goals = EXCLUDED.half_time_away_goals,
                    second_half_home_goals = EXCLUDED.second_half_home_goals,
                    second_half_away_goals = EXCLUDED.second_half_away_goals,
                    home_goals_normaltime = EXCLUDED.home_goals_normaltime,
                    away_goals_normaltime = EXCLUDED.away_goals_normaltime,
                    injury_time_first_half = EXCLUDED.injury_time_first_half,
                    injury_time_second_half = EXCLUDED.injury_time_second_half,
                    attendance = EXCLUDED.attendance,
                    importance = EXCLUDED.importance,
                    has_xg = EXCLUDED.has_xg,
                    has_event_player_statistics = EXCLUDED.has_event_player_statistics,
                    referee_id = EXCLUDED.referee_id,
                    updated_at = NOW()
                RETURNING id;
            ''')
            
            params = {
                "season_id": match.season.internal_id, "dt": match.match_datetime, "match_week": match.match_week, 
                "h_id": match.home_team.internal_id, "a_id": match.away_team.internal_id,
                "st_id": match.stadium.internal_id if match.stadium else None,
                "ref_id": match.referee.internal_id if match.referee else None,
                "status": match.status.value, "status_label": match.status_label,
                "hg": match.home_goals, "ag": match.away_goals,
                "outcome": outcome_value, "outcome_label": match.outcome_label, "outcome_code": match.outcome_code,
                "hthg": match.half_time_home_goals, "htag": match.half_time_away_goals,
                "shhg": match.second_half_home_goals, "shag": match.second_half_away_goals,
                "hg_normal": match.home_goals_normaltime, "ag_normal": match.away_goals_normaltime,
                "it1": match.injury_time_first_half, "it2": match.injury_time_second_half,
                "attendance": match.attendance, "importance": match.importance,
                "has_xg": match.has_xg, "has_events": match.has_event_player_statistics,
            }
            
            result = self.session.execute(query, params)
            match.internal_id = result.scalar_one_or_none()
            
            if match.internal_id and match.external_id:
                upsert_mapping(str(match.external_id), match.internal_id, "match", "sofascore", session=self.session)
            
            return match.internal_id
                    
        except Exception as e:
            logger.error(f"Error upserting match ExtID '{getattr(match, 'external_id', 'Unknown')}': {e}", exc_info=True)
            raise LoaderError(f"Failed to upsert match: {e}")
    
    def upsert_match_events(self, events: List[ParsedMatchEvent], match_internal_id: int):
        """Upsert hàng loạt sự kiện trận đấu."""
        if not events or not match_internal_id:
            return

        try:
            # Delete old events to ensure data consistency
            self.session.execute(
                text('DELETE FROM "MatchEvents" WHERE match_id = :mid'), 
                {"mid": match_internal_id}
            )

            events_to_insert = []
            for event in events:
                # Upsert related entities and get their internal IDs
                team_id = self.upsert_team(event.team) if event.team else None
                player_id = self.upsert_player(event.player) if event.player else None
                related_player_id = self.upsert_player(event.related_player) if event.related_player else None

                events_to_insert.append({
                    "match_id": match_internal_id,
                    "minute": event.minute,
                    "event_type": event.event_type.value,
                    "team_id": team_id,
                    "player_id": player_id,
                    "related_player_id": related_player_id,
                    "period": event.period.value,
                    "description": event.description[:500] if event.description else None,
                    "raw_event_data": event.raw_event_data # Assuming a JSON/JSONB column
                })
            
            if not events_to_insert:
                return

            # Bulk insert using execute with a list of dicts
            query = text('''
                INSERT INTO "MatchEvents" (
                    match_id, minute, event_type, team_id, player_id, 
                    related_player_id, period, description, raw_event_data
                ) VALUES (
                    :match_id, :minute, :event_type, :team_id, :player_id,
                    :related_player_id, :period, :description, :raw_event_data
                )
            ''')
            self.session.execute(query, events_to_insert)

        except Exception as e:
            logger.error(f"Failed to bulk insert match events for match_id {match_internal_id}: {e}", exc_info=True)
            raise LoaderError(f"Failed to insert match events: {e}")
        
    def load_full_match_data(self, match: ParsedMatch) -> Optional[int]:
        """Điều phối việc tải một trận đấu hoàn chỉnh với transaction management."""
        if not match: return None
        
        logger.debug(f"Starting to load full data for match ExtID: {match.external_id}")
        
        try:
            with self.session.begin(): # Start a single transaction for the whole operation
                # Upsert related entities first
                self.upsert_season(match.season)
                self.upsert_team(match.home_team)
                self.upsert_team(match.away_team)
                self.upsert_stadium(match.stadium)
                self.upsert_referee(match.referee)
                
                match_id = self.upsert_match(match)
                
                if match_id and match.events:
                    self.upsert_match_events(match.events, match_id)

                if match_id:
                    logger.info(f"Successfully loaded complete match data: ExtID {match.external_id} -> IntID {match_id}")
                
                return match_id
                        
        except Exception as e:
            logger.error(f"Full load failed for match ExtID {getattr(match, 'external_id', 'Unknown')}. Transaction rolled back. Error: {e}", exc_info=True)
            # Re-raise as a LoaderError to be caught by bulk loader
            raise LoaderError(f"Failed to fully load match data: {e}")

    def bulk_load_matches(self, matches: List[ParsedMatch]) -> Dict[str, Any]:
        """Tải hàng loạt các trận đấu với tracking chi tiết."""
        if not matches: return {"total": 0, "success": 0, "failed": 0, "failed_matches": []}
            
        results = {"total": len(matches), "success": 0, "failed": 0, "failed_matches": []}
        logger.info(f"Starting bulk load of {len(matches)} matches")
        
        for i, match in enumerate(matches):
            try:
                # Each match is its own transaction
                match_id = self.load_full_match_data(match)
                if match_id:
                    results["success"] += 1
                else:
                    # This case should ideally not be reached if exceptions are raised properly
                    results["failed"] += 1
                    results["failed_matches"].append({
                        "external_id": getattr(match, 'external_id', f'index_{i}'),
                        "reason": "Loader returned None without raising an exception."
                    })
            except LoaderError as e: # Catch our specific, more informative errors
                results["failed"] += 1
                results["failed_matches"].append({
                    "external_id": getattr(match, 'external_id', f'index_{i}'),
                    "reason": str(e)
                })
            except Exception as e: # Catch any other unexpected errors
                results["failed"] += 1
                results["failed_matches"].append({
                    "external_id": getattr(match, 'external_id', f'index_{i}'),
                    "reason": f"An unexpected error occurred: {str(e)}"
                })
                logger.error(f"Unexpected fatal error in bulk load for match {i}: {e}", exc_info=True)
        
        self.clear_cache()
        logger.info("Bulk load completed.", extra=results)
        return results

    def clear_cache(self):
        """Clear the entity cache."""
        self._entity_cache.clear()
        logger.debug("Entity cache cleared")