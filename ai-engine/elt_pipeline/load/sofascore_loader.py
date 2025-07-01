# elt_pipeline/load/sofascore_loader.py

"""
SofaScore ETL Pipeline: Loader - FIXED VERSION
Sửa các lỗi nghiêm trọng và cải thiện performance.
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

# --- CONSTANTS ---
ALLOWED_TABLES = {
    "Leagues": {
        "table": "Leagues",
        "columns": ["name", "country", "established_year"],
        "conflict_columns": ["name"]
    },
    "Seasons": {
        "table": "Seasons",
        "columns": ["league_id", "start_year", "end_year", "name"],
        "conflict_columns": ["league_id", "name"]
    },
    "Stadiums": {
        "table": "Stadiums",
        "columns": ["name", "city", "capacity", "timezone"],
        "conflict_columns": ["name"]
    },
    "Teams": {
        "table": "Teams",
        "columns": ["name", "short_name", "stadium_id", "established_year", "logo_url"],
        "conflict_columns": ["name"]
    },
    "Referees": {
        "table": "Referees",
        "columns": ["name", "date_of_birth", "country"],
        "conflict_columns": ["name", "date_of_birth"]
    },
    "Players": {
        "table": "Players",
        "columns": ["name", "position", "date_of_birth", "nationality", "height"],
        "conflict_columns": ["name", "date_of_birth"]
    },
}

class LoaderError(Exception):
    """Custom exception for loader errors."""
    pass

class SofaScoreLoader:
    """
    Chịu trách nhiệm ghi các đối tượng đã chuẩn hóa vào DB.
    FIXED VERSION: Improved transaction management, error handling, and security.
    """

    def __init__(self, session: Session):
        self.session = session
        self._validate_session()
        # Cache để tránh duplicate queries
        self._entity_cache: Dict[str, Dict[str, int]] = {
            "teams": {},
            "players": {},
            "referees": {},
            "stadiums": {},
            "leagues": {},
            "seasons": {}
        }
    
    def _validate_session(self):
        """Validate database session with better error handling."""
        if not self.session:
            raise ValueError("Database session is required")
        try:
            self.session.execute(text("SELECT 1"))
        except Exception as e:
            logger.error(f"Database session validation failed: {e}")
            raise LoaderError(f"Invalid database session: {e}")

    def _get_table_config(self, table_name: str) -> Dict[str, Any]:
        """Get table configuration with validation."""
        config = ALLOWED_TABLES.get(table_name)
        if not config:
            raise LoaderError(f"Table '{table_name}' not in allowed tables")
        return config

    def _build_upsert_query(self, table_config: Dict[str, Any]) -> str:
        """Build safe upsert query with enhanced security."""
        table_name = table_config["table"]
        columns = table_config["columns"]
        conflict_columns = table_config["conflict_columns"]
        
        # Additional validation for security
        if not all(isinstance(col, str) and col.isidentifier() for col in columns):
            raise LoaderError("Invalid column names detected")
        
        column_str = ", ".join([f'"{col}"' for col in columns])
        column_placeholders = ", ".join([f":{col}" for col in columns])
        update_columns = [col for col in columns if col not in conflict_columns]
        update_sets = ", ".join([f'"{col}" = EXCLUDED."{col}"' for col in update_columns])
        conflict_cols = ", ".join([f'"{col}"' for col in conflict_columns])
        
        do_update_clause = f"DO UPDATE SET {update_sets}" if update_sets else "DO NOTHING"

        query = f'''
            INSERT INTO "{table_name}" ({column_str}) 
            VALUES ({column_placeholders})
            ON CONFLICT ({conflict_cols}) 
            {do_update_clause}
            RETURNING id;
        '''
        return query

    def _get_cache_key(self, entity_type: str, identifier: str) -> str:
        """Generate cache key for entities."""
        return f"{entity_type}:{identifier}"

    def _check_entity_cache(self, entity_type: str, identifier: str) -> Optional[int]:
        """Check if entity exists in cache."""
        cache_key = f"{entity_type}:{identifier}"
        return self._entity_cache.get(entity_type, {}).get(cache_key)

    def _cache_entity(self, entity_type: str, identifier: str, internal_id: int):
        """Cache entity for future lookups."""
        cache_key = f"{entity_type}:{identifier}"
        if entity_type not in self._entity_cache:
            self._entity_cache[entity_type] = {}
        self._entity_cache[entity_type][cache_key] = internal_id

    @contextmanager
    def _transaction_context(self):
        """Context manager for database transactions."""
        try:
            yield
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
            raise

    def upsert_league(self, league: ParsedLeague) -> Optional[int]:
        """Upsert một giải đấu với caching và error handling cải thiện."""
        if not league or not league.name:
            return None
            
        try:
            # Check existing internal_id
            if league.internal_id:
                return league.internal_id

            # Check cache
            cache_key = f"league:{league.name}:{league.country}"
            cached_id = self._check_entity_cache("leagues", cache_key)
            if cached_id:
                league.internal_id = cached_id
                return cached_id

            table_config = self._get_table_config("Leagues")
            query = self._build_upsert_query(table_config)
            params = {
                "name": league.name.strip(),
                "country": league.country.strip() if league.country else None,
                "established_year": league.established_year
            }
            
            result = self.session.execute(text(query), params)
            league.internal_id = result.scalar_one_or_none()
            
            if league.internal_id:
                self._cache_entity("leagues", cache_key, league.internal_id)
                logger.debug(f"Upserted League: {league.name} (ID: {league.internal_id})")
            
            return league.internal_id
            
        except SQLAlchemyError as e:
            logger.error(f"Database error upserting league {league.name}: {e}")
            raise LoaderError(f"Failed to upsert league: {e}")
        except Exception as e:
            logger.error(f"Unexpected error upserting league {league.name}: {e}")
            raise LoaderError(f"Unexpected error: {e}")

    def upsert_season(self, season: ParsedSeason) -> Optional[int]:
        """Upsert một mùa giải với improved error handling."""
        if not season or not season.name:
            return None
            
        try:
            if season.internal_id:
                return season.internal_id

            # Cache check
            cache_key = f"season:{season.name}:{season.league.name if season.league else 'unknown'}"
            cached_id = self._check_entity_cache("seasons", cache_key)
            if cached_id:
                season.internal_id = cached_id
                return cached_id

            # Ensure league exists
            league_id = self.upsert_league(season.league)
            if not league_id:
                raise LoaderError(f"Could not get ID for league: {season.league.name if season.league else 'Unknown'}")

            table_config = self._get_table_config("Seasons")
            query = self._build_upsert_query(table_config)
            params = {
                "league_id": league_id,
                "start_year": season.start_year,
                "end_year": season.end_year,
                "name": season.name.strip()
            }
            
            result = self.session.execute(text(query), params)
            season.internal_id = result.scalar_one_or_none()
            
            if season.internal_id:
                self._cache_entity("seasons", cache_key, season.internal_id)
                logger.debug(f"Upserted Season: {season.name} (ID: {season.internal_id})")
            
            return season.internal_id
            
        except LoaderError:
            raise
        except Exception as e:
            logger.error(f"Error upserting season {season.name}: {e}")
            raise LoaderError(f"Failed to upsert season: {e}")

    def upsert_stadium(self, stadium: ParsedStadium) -> Optional[int]:
        """Upsert một sân vận động với validation."""
        if not stadium or not stadium.name:
            return None
            
        try:
            if stadium.internal_id:
                return stadium.internal_id

            # Cache check
            cache_key = f"stadium:{stadium.name.strip()}"
            cached_id = self._check_entity_cache("stadiums", cache_key)
            if cached_id:
                stadium.internal_id = cached_id
                return cached_id

            table_config = self._get_table_config("Stadiums")
            query = self._build_upsert_query(table_config)
            params = {
                "name": stadium.name.strip(),
                "city": stadium.city.strip() if stadium.city else None,
                "capacity": stadium.capacity,
                "timezone": stadium.timezone
            }
            
            result = self.session.execute(text(query), params)
            stadium.internal_id = result.scalar_one_or_none()
            
            if stadium.internal_id:
                self._cache_entity("stadiums", cache_key, stadium.internal_id)
                logger.debug(f"Upserted stadium: {stadium.name} (ID: {stadium.internal_id})")
            
            return stadium.internal_id
            
        except Exception as e:
            logger.error(f"Error upserting stadium {getattr(stadium, 'name', 'Unknown')}: {e}")
            raise LoaderError(f"Failed to upsert stadium: {e}")

    def upsert_team(self, team: ParsedTeam) -> Optional[int]:
        """Upsert một đội bóng với caching và mapping."""
        if not team or not team.name:
            return None
            
        try:
            if team.internal_id:
                return team.internal_id

            # Check mapping first
            if team.external_id:
                internal_id = get_internal_id(str(team.external_id), "team", "sofascore", self.session)
                if internal_id:
                    team.internal_id = internal_id
                    return internal_id

            # Cache check
            cache_key = f"team:{team.name.strip()}"
            cached_id = self._check_entity_cache("teams", cache_key)
            if cached_id:
                team.internal_id = cached_id
                return cached_id

            # Upsert dependencies
            stadium_id = self.upsert_stadium(team.stadium) if team.stadium else None

            # Custom query với logic cập nhật an toàn
            query = text("""
                INSERT INTO "Teams" (name, short_name, stadium_id, established_year, logo_url)
                VALUES (:name, :short_name, :stadium_id, :established_year, :logo_url)
                ON CONFLICT (name) DO UPDATE SET
                    short_name = COALESCE(EXCLUDED.short_name, "Teams".short_name),
                    stadium_id = COALESCE(EXCLUDED.stadium_id, "Teams".stadium_id),
                    established_year = COALESCE(EXCLUDED.established_year, "Teams".established_year),
                    logo_url = COALESCE(EXCLUDED.logo_url, "Teams".logo_url),
                    updated_at = NOW()
                RETURNING id;
            """)
            
            params = {
                "name": team.name.strip(),
                "short_name": team.short_name.strip() if team.short_name else None,
                "stadium_id": stadium_id,
                "established_year": team.established_year,
                "logo_url": team.logo_url
            }
            
            result = self.session.execute(query, params)
            team.internal_id = result.scalar_one_or_none()

            if team.internal_id:
                # Create mapping if external_id exists
                if team.external_id:
                    upsert_mapping(str(team.external_id), team.internal_id, "team", "sofascore", self.session)
                self._cache_entity("teams", cache_key, team.internal_id)
                logger.debug(f"Upserted Team: {team.name} (ID: {team.internal_id})")
            
            return team.internal_id
            
        except Exception as e:
            logger.error(f"Failed to upsert team {getattr(team, 'name', 'Unknown')}: {e}")
            raise LoaderError(f"Failed to upsert team: {e}")

    def upsert_referee(self, referee: ParsedReferee) -> Optional[int]:
        """Upsert một trọng tài với validation cải thiện."""
        if not referee or not referee.name:
            return None
            
        try:
            if referee.internal_id:
                return referee.internal_id

            # Check mapping first
            if referee.external_id:
                internal_id = get_internal_id(str(referee.external_id), "referee", "sofascore", self.session)
                if internal_id:
                    referee.internal_id = internal_id
                    return internal_id

            table_config = self._get_table_config("Referees")
            query = self._build_upsert_query(table_config)
            params = {
                "name": referee.name.strip(),
                "date_of_birth": referee.date_of_birth,
                "country": referee.country.strip() if referee.country else None
            }
            
            result = self.session.execute(text(query), params)
            referee.internal_id = result.scalar_one_or_none()

            if referee.internal_id:
                if referee.external_id:
                    upsert_mapping(str(referee.external_id), referee.internal_id, "referee", "sofascore", self.session)
                logger.debug(f"Upserted Referee: {referee.name} (ID: {referee.internal_id})")
            
            return referee.internal_id
            
        except Exception as e:
            logger.error(f"Failed to upsert referee {getattr(referee, 'name', 'Unknown')}: {e}")
            raise LoaderError(f"Failed to upsert referee: {e}")

    def upsert_player(self, player: ParsedPlayer) -> Optional[int]:
        """Upsert một cầu thủ với caching."""
        if not player or not player.name:
            return None
            
        try:
            if player.internal_id:
                return player.internal_id

            # Check mapping first
            if player.external_id:
                internal_id = get_internal_id(str(player.external_id), "player", "sofascore", self.session)
                if internal_id:
                    player.internal_id = internal_id
                    return internal_id

            table_config = self._get_table_config("Players")
            query = self._build_upsert_query(table_config)
            params = {
                "name": player.name.strip(),
                "position": player.position,
                "date_of_birth": player.date_of_birth,
                "nationality": player.nationality.strip() if player.nationality else None,
                "height": player.height
            }
            
            result = self.session.execute(text(query), params)
            player.internal_id = result.scalar_one_or_none()

            if player.internal_id:
                if player.external_id:
                    upsert_mapping(str(player.external_id), player.internal_id, "player", "sofascore", self.session)
                logger.debug(f"Upserted Player: {player.name} (ID: {player.internal_id})")
            
            return player.internal_id
            
        except Exception as e:
            logger.error(f"Failed to upsert player {getattr(player, 'name', 'Unknown')}: {e}")
            raise LoaderError(f"Failed to upsert player: {e}")

    def upsert_match(self, match: ParsedMatch) -> Optional[int]:
        """Upserts a single match record with enum validation."""
        try:
            # Check existing mapping
            if match.external_id:
                internal_id = get_internal_id(str(match.external_id), "match", "sofascore", self.session)
                if internal_id:
                    logger.debug(f"Match mapping exists, skipping upsert. ExtID: {match.external_id}")
                    match.internal_id = internal_id
                    return internal_id
            
            # Validate required fields
            if not all([match.home_team.internal_id, match.away_team.internal_id, match.season.internal_id]):
                raise LoaderError("Missing internal IDs for team or season.")

            # Use enum values instead of string comparison
            outcome_value = match.outcome.value if match.status == MatchStatus.FINISHED else None
            
            query = text('''
                INSERT INTO "Matches" (
                    season_id, match_datetime, match_week, home_team_id, away_team_id, 
                    stadium_id, referee_id, home_goals, away_goals, 
                    half_time_home_goals, half_time_away_goals, outcome, status
                )
                VALUES (
                    :season_id, :dt, :match_week, :h_id, :a_id, :st_id, :ref_id, :hg, :ag, 
                    :hthg, :htag, :outcome, :status
                )
                ON CONFLICT (match_datetime, home_team_id, away_team_id) DO UPDATE SET
                    home_goals = EXCLUDED.home_goals,
                    away_goals = EXCLUDED.away_goals,
                    half_time_home_goals = EXCLUDED.half_time_home_goals,
                    half_time_away_goals = EXCLUDED.half_time_away_goals,
                    status = EXCLUDED.status,
                    outcome = EXCLUDED.outcome,
                    updated_at = NOW()
                RETURNING id;
            ''')
            
            params = {
                "season_id": match.season.internal_id,
                "dt": match.match_datetime,
                "match_week": match.match_week, 
                "h_id": match.home_team.internal_id,
                "a_id": match.away_team.internal_id,
                "st_id": match.stadium.internal_id if match.stadium else None,
                "ref_id": match.referee.internal_id if match.referee else None,
                "hg": match.home_goals,
                "ag": match.away_goals,
                "hthg": match.half_time_home_goals,
                "htag": match.half_time_away_goals,
                "status": match.status.value,  # Use enum value
                "outcome": outcome_value
            }
            
            result = self.session.execute(query, params)
            match.internal_id = result.scalar_one_or_none()
            
            if match.internal_id and match.external_id:
                upsert_mapping(str(match.external_id), match.internal_id, "match", "sofascore", self.session)
                logger.debug(f"Upserted Match: ExtID {match.external_id}, IntID {match.internal_id}")
            
            return match.internal_id
                    
        except LoaderError:
            raise
        except Exception as e:
            logger.error(f"Failed to upsert match: ExtID {getattr(match, 'external_id', 'Unknown')}: {e}")
            raise LoaderError(f"Failed to upsert match: {e}")
    
    def backup_match_events(self, match_internal_id: int) -> List[Dict[str, Any]]:
        """Backup existing match events before deletion."""
        try:
            query = text('''
                SELECT * FROM "MatchEvents" WHERE match_id = :match_id
            ''')
            result = self.session.execute(query, {"match_id": match_internal_id})
            return [dict(row._mapping) for row in result]
        except Exception as e:
            logger.warning(f"Failed to backup match events for match {match_internal_id}: {e}")
            return []

    def upsert_match_event(self, event: ParsedMatchEvent, match_internal_id: int):
        """Inserts a single match event record with better error handling."""
        if not event or not match_internal_id:
            return
            
        try:
            # Upsert related entities
            team_id = self.upsert_team(event.team) if event.team else None
            player_id = self.upsert_player(event.player) if event.player else None
            related_player_id = self.upsert_player(event.related_player) if event.related_player else None

            query = text('''
                INSERT INTO "MatchEvents" (
                    match_id, minute, event_type, team_id, player_id, 
                    related_player_id, period, description
                ) VALUES (
                    :match_id, :minute, :event_type, :team_id, :player_id,
                    :related_player_id, :period, :description
                )
            ''')
            params = {
                "match_id": match_internal_id,
                "minute": event.minute,
                "event_type": event.event_type,
                "team_id": team_id,
                "player_id": player_id,
                "related_player_id": related_player_id,
                "period": event.period,
                "description": event.description[:500] if event.description else None  # Truncate long descriptions
            }
            self.session.execute(query, params)
            
        except Exception as e:
            logger.error(f"Failed to insert match event for match_id {match_internal_id}: {e}")
            raise LoaderError(f"Failed to insert match event: {e}")
        
    def load_full_match_data(self, match: ParsedMatch) -> Optional[int]:
        """Điều phối việc tải một trận đấu hoàn chỉnh với transaction management."""
        if not match:
            return None
            
        with self._transaction_context():
            try:
                # Upsert all related entities first
                self.upsert_season(match.season)
                self.upsert_team(match.home_team)
                self.upsert_team(match.away_team)
                self.upsert_stadium(match.stadium)
                self.upsert_referee(match.referee)
                
                # Upsert the match
                match_id = self.upsert_match(match)
                
                if match_id and match.events:
                    # Backup existing events (optional safety measure)
                    # backup_events = self.backup_match_events(match_id)
                    
                    # Delete old events to prevent duplicates
                    self.session.execute(
                        text('DELETE FROM "MatchEvents" WHERE match_id = :mid'), 
                        {"mid": match_id}
                    )
                    
                    # Insert new events
                    for event in match.events:
                        self.upsert_match_event(event, match_id)

                if match_id:
                    logger.info(f"Successfully loaded complete match data: ExtID {match.external_id}, IntID {match_id}")
                
                return match_id
                        
            except LoaderError:
                raise
            except Exception as e:
                logger.error(f"Error during full match data loading: ExtID {getattr(match, 'external_id', 'Unknown')}: {e}")
                raise LoaderError(f"Failed to load match data: {e}")

    def bulk_load_matches(self, matches: List[ParsedMatch]) -> Dict[str, Any]:
        """Tải hàng loạt các trận đấu với transaction management và detailed tracking."""
        if not matches:
            return {"total": 0, "success": 0, "failed": 0, "failed_matches": []}
            
        results = {
            "total": len(matches), 
            "success": 0, 
            "failed": 0, 
            "failed_matches": []
        }
        
        logger.info(f"Starting bulk load of {len(matches)} matches")
        
        for i, match in enumerate(matches):
            try:
                match_id = self.load_full_match_data(match)
                if match_id:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    results["failed_matches"].append({
                        "external_id": getattr(match, 'external_id', f'index_{i}'),
                        "reason": "Loader returned None"
                    })
                    
                # Log progress every 100 matches
                if (i + 1) % 100 == 0:
                    logger.info(f"Processed {i + 1}/{len(matches)} matches")
                    
            except LoaderError as e:
                results["failed"] += 1
                results["failed_matches"].append({
                    "external_id": getattr(match, 'external_id', f'index_{i}'),
                    "reason": str(e)
                })
            except Exception as e:
                results["failed"] += 1
                results["failed_matches"].append({
                    "external_id": getattr(match, 'external_id', f'index_{i}'),
                    "reason": f"Unexpected error: {str(e)}"
                })
                logger.error(f"Unexpected error in bulk load for match {i}: {e}")
        
        # Clear cache after bulk operation
        self._entity_cache.clear()
        
        logger.info("Bulk load completed", extra=results)
        return results

    def clear_cache(self):
        """Clear the entity cache."""
        self._entity_cache.clear()
        logger.debug("Entity cache cleared")