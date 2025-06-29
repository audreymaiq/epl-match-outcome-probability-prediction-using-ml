# elt_pipeline\load\sofascore_loader.py

"""
SofaScore ETL Pipeline: Loader - Ghi các đối tượng đã chuẩn hóa vào database.

"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text

from utils.db_connector import DatabaseConnector
from utils.external_mapping import get_internal_id, upsert_mapping
from elt_pipeline.transform.sofascore_transformer import (
    ParsedTeam, ParsedStadium, ParsedReferee, ParsedMatch
)

from elt_pipeline.transform.data_structures import (
    ParsedTeam, ParsedStadium, ParsedReferee, ParsedMatch, ParsedLeague, ParsedSeason
)

logger = logging.getLogger(__name__)

# --- CONSTANTS ---
ALLOWED_TABLES = {
    "Teams": {
        "table": "Teams",
        "columns": ["name"],
        "conflict_columns": ["name"]
    },
    "Referees": {
        "table": "Referees", 
        "columns": ["name"],
        "conflict_columns": ["name"]
    },
    "Players": {
        "table": "Players",
        "columns": ["name"], 
        "conflict_columns": ["name"]
    },
    "Stadiums": {
        "table": "Stadiums",
        "columns": ["name", "city", "capacity"],
        "conflict_columns": ["name"]
    },
    "Leagues": {
        "table": "Leagues",
        "columns": ["name", "country"],
        "conflict_columns": ["name"]
    },
    "Seasons": {
        "table": "Seasons",
        "columns": ["league_id", "start_year", "end_year", "name"],
        "conflict_columns": ["name"] # Giả sử tên mùa giải là duy nhất
    }
}

# --- LỚP LOADER: CHỈ GHI VÀO DATABASE ---
class SofaScoreLoader:
    """Chịu trách nhiệm ghi các đối tượng đã chuẩn hóa vào DB."""

    def __init__(self, session: Session):
        self.session = session
        self._validate_session()
    
    def _validate_session(self):
        """Validate database session."""
        if not self.session:
            raise ValueError("Database session is required")
        
        try:
            # Test connection
            self.session.execute("SELECT 1")
        except Exception as e:
            logger.error(f"Database session validation failed: {e}")
            raise

    def _get_table_config(self, table_name: str) -> Optional[Dict[str, Any]]:
        """Get table configuration safely."""
        return ALLOWED_TABLES.get(table_name)

    def _build_upsert_query(self, table_config: Dict[str, Any]) -> str:
        """Build safe upsert query using table configuration."""
        table_name = table_config["table"]
        columns = table_config["columns"]
        conflict_columns = table_config["conflict_columns"]
        
        # Build column placeholders
        column_placeholders = ", ".join([f":{col}" for col in columns])
        update_sets = ", ".join([f"{col} = EXCLUDED.{col}" for col in columns])
        conflict_cols = ", ".join(conflict_columns)
        
        query = f'''
            INSERT INTO "{table_name}" ({", ".join(columns)}) 
            VALUES ({column_placeholders})
            ON CONFLICT ({conflict_cols}) 
            DO UPDATE SET {update_sets}
            RETURNING id;
        '''
        
        return query

    def _upsert_and_map(self, entity_type: str, external_id: int, name: str, table_name: str) -> Optional[int]:
        """
        Hàm chung để upsert Team/Referee/Player và tạo mapping.
        """
        try:
            # Get table configuration
            table_config = self._get_table_config(table_name)
            if not table_config:
                logger.error(f"Invalid table name for _upsert_and_map: {table_name}")
                return None

            # Kiểm tra mapping hiện tại
            internal_id = get_internal_id(
                str(external_id), entity_type, "sofascore", session=self.session
            )
            if internal_id:
                logger.debug(f"{entity_type} mapping already exists", extra={
                    "external_id": external_id, "internal_id": internal_id
                })
                return internal_id

            # Build và execute safe query
            query = self._build_upsert_query(table_config)
            params = {"name": name.strip()}
            
            result = self.session.execute(query, params)
            internal_id = result.scalar_one_or_none()
            
            if internal_id:
                # Tạo mapping
                upsert_mapping(
                    str(external_id), internal_id, entity_type, "sofascore", 
                    session=self.session
                )
                
                logger.debug(f"Successfully upserted {entity_type}", extra={
                    "external_id": external_id, 
                    "internal_id": internal_id, 
                    "name": name
                })
                return internal_id
            else:
                logger.error(f"Upsert returned no ID for {entity_type}", extra={
                    "external_id": external_id, "name": name
                })
                return None
                    
        except IntegrityError as e:
            logger.error(f"Integrity error upserting {entity_type}", extra={
                "external_id": external_id, "name": name, "error": str(e)
            })
            raise  # Let the orchestrator handle transaction rollback
        except SQLAlchemyError as e:
            logger.error(f"Database error upserting {entity_type}", extra={
                "external_id": external_id, "name": name, "error": str(e)
            })
            raise
        except Exception as e:
            logger.error(f"Unexpected error upserting {entity_type}", extra={
                "external_id": external_id, "name": name, "error": str(e)
            }, exc_info=True)
            raise

    def upsert_league(self, league: ParsedLeague) -> Optional[int]:
        """Upsert một giải đấu và cập nhật internal_id của nó."""
        try:
            if league.internal_id:
                return league.internal_id

            table_config = self._get_table_config("Leagues")
            query = self._build_upsert_query(table_config)
            
            params = {"name": league.name, "country": league.country}
            
            result = self.session.execute(text(query), params) # Sử dụng text()
            league.internal_id = result.scalar_one_or_none()
            
            if league.internal_id:
                logger.debug(f"Upserted League: {league.name} (ID: {league.internal_id})")
            return league.internal_id
        except Exception:
            logger.error(f"Failed to upsert league: {league.name}", exc_info=True)
            raise

    def upsert_season(self, season: ParsedSeason) -> Optional[int]:
        """Upsert một mùa giải và cập nhật internal_id của nó."""
        try:
            if season.internal_id:
                return season.internal_id

            # Đảm bảo league đã có internal_id
            league_id = self.upsert_league(season.league)
            if not league_id:
                raise ValueError(f"Could not get internal ID for league: {season.league.name}")

            table_config = self._get_table_config("Seasons")
            query = self._build_upsert_query(table_config)
            
            params = {
                "league_id": league_id,
                "start_year": season.start_year,
                "end_year": season.end_year,
                "name": season.name
            }
            
            result = self.session.execute(text(query), params) # Sử dụng text()
            season.internal_id = result.scalar_one_or_none()
            
            if season.internal_id:
                logger.debug(f"Upserted Season: {season.name} (ID: {season.internal_id})")
            return season.internal_id
        except Exception:
            logger.error(f"Failed to upsert season: {season.name}", exc_info=True)
            raise

    def upsert_team(self, team: ParsedTeam) -> Optional[int]:
        """Upsert a team and update its internal_id. Assumes team object is valid."""
        try:
            if team.internal_id:
                return team.internal_id
            
            team.internal_id = self._upsert_and_map(
                entity_type="team", 
                external_id=team.external_id, 
                name=team.name, 
                table_name="Teams"
            )
            return team.internal_id
        except Exception as e:
            logger.error("Failed in upsert_team", extra={"team_external_id": getattr(team, 'external_id', None), "error": str(e)}, exc_info=True)
            raise

    def upsert_stadium(self, stadium: ParsedStadium) -> Optional[int]:
        """Upsert a stadium and update its internal_id. Assumes stadium object is valid."""
        try:
            if stadium.internal_id:
                return stadium.internal_id
            
            table_config = self._get_table_config("Stadiums")
            if not table_config:
                logger.error("Stadiums table configuration not found.")
                return None

            query = self._build_upsert_query(table_config)
            
            params = {
                "name": stadium.name.strip(),
                "city": stadium.city.strip() if stadium.city else None,
                "capacity": stadium.capacity
            }
            
            result = self.session.execute(query, params)
            stadium.internal_id = result.scalar_one_or_none()
            
            if stadium.internal_id:
                logger.debug("Successfully upserted stadium", extra={"stadium_name": stadium.name, "stadium_id": stadium.internal_id})
            
            return stadium.internal_id
                
        except Exception:
            logger.error("Error upserting stadium", extra={"stadium_name": getattr(stadium, 'name', None)}, exc_info=True)
            raise

    def upsert_referee(self, referee: ParsedReferee) -> Optional[int]:
        """Upsert a referee and update its internal_id. Assumes referee object is valid."""
        try:
            if referee.internal_id:
                return referee.internal_id

            referee.internal_id = self._upsert_and_map(
                entity_type="referee", 
                external_id=referee.external_id, 
                name=referee.name, 
                table_name="Referees"
            )
            return referee.internal_id
        
        except Exception as e:
            logger.error("Failed in upsert_referee", extra={"referee_external_id": getattr(referee, 'external_id', None), "error": str(e)}, exc_info=True)
            raise

    def upsert_match(self, match: ParsedMatch) -> Optional[int]:
        """
        Upserts a single match record. 
        ASSUMES: 
        1. The match object is validated.
        2. All related entities (teams, stadium, referee) have their internal_id populated.
        """
        try:
            # Kiểm tra mapping hiện tại
            internal_id = get_internal_id(str(match.external_id), "match", "sofascore", session=self.session)
            if internal_id:
                # Ghi chú: Chúng ta có thể cập nhật trận đấu ở đây nếu cần, nhưng hiện tại chỉ trả về ID
                logger.debug("Match mapping already exists, skipping upsert.", extra={"ext_id": match.external_id, "int_id": internal_id})
                match.internal_id = internal_id
                return internal_id
            
            query = text('''
                INSERT INTO "Matches" (
                    season_id, match_datetime, match_week, home_team_id, away_team_id, 
                    stadium_id, referee_id, home_goals, away_goals, 
                    half_time_home_goals, half_time_away_goals, outcome, status
                )
                VALUES (
                    :season_id, :dt, :round, :h_id, :a_id, :st_id, :ref_id, :hg, :ag, 
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
            
            # Đảm bảo các ID phụ thuộc không phải là None trước khi truy vấn
            home_team_id = match.home_team.internal_id
            away_team_id = match.away_team.internal_id
            season_id = match.season.internal_id 
            if not all([home_team_id, away_team_id, season_id]):
                raise ValueError("Missing internal IDs for team or season.")

            params = {
                "season_id": season_id,
                "dt": match.match_datetime,
                "h_id": home_team_id,
                "a_id": away_team_id,
                "hg": match.home_goals,
                "ag": match.away_goals,
                "hthg": match.ht_home_goals,
                "htag": match.ht_away_goals,
                "status": match.status.strip(),
                "round": str(match.round) if match.round else None,
                "st_id": match.stadium.internal_id if match.stadium else None,
                "ref_id": match.referee.internal_id if match.referee else None,
            }
            
            result = self.session.execute(query, params)
            match.internal_id = result.scalar_one_or_none()
            
            if match.internal_id:
                upsert_mapping(str(match.external_id), match.internal_id, "match", "sofascore", session=self.session)
                logger.debug("Successfully upserted match", extra={"ext_id": match.external_id, "int_id": match.internal_id})
                return match.internal_id
            else:
                logger.warning("Match upsert returned no ID", extra={"ext_id": match.external_id})
                return None
                    
        except Exception:
            logger.error("Failed to upsert match", extra={"match_ext_id": getattr(match, 'external_id', None)}, exc_info=True)
            raise
        
    def load_full_match_data(self, match: ParsedMatch) -> Optional[int]:
        """
        Điều phối việc tải một trận đấu hoàn chỉnh và các thực thể liên quan của nó.
        """
        try:
            # Upsert các thực thể phụ thuộc và điền internal_id vào object `match`
            self.upsert_season(match.season) # Lệnh này sẽ tự động upsert league
            self.upsert_team(match.home_team)
            self.upsert_team(match.away_team)
            if match.stadium:
                self.upsert_stadium(match.stadium)
            if match.referee:
                self.upsert_referee(match.referee)
            
            # Giờ đây, tất cả các internal_id cần thiết đã có trong object `match`
            # và chúng ta có thể upsert trận đấu chính
            match_id = self.upsert_match(match)
            
            if match_id:
                logger.info("Successfully loaded complete match data", extra={"match_ext_id": match.external_id, "match_int_id": match_id})
            return match_id
                    
        except Exception:
            logger.error(f"Error during full match data loading", extra={"match_ext_id": getattr(match, 'external_id', None)}, exc_info=True)
            raise # Ném lỗi để transaction bên ngoài có thể rollback

    def bulk_load_matches(self, matches: list[ParsedMatch]) -> Dict[str, Any]:
        """
        Bulk load multiple matches with comprehensive error tracking.
        
        Args:
            matches: List of ParsedMatch objects
            
        Returns:
            Dictionary with success/failure statistics
        """
        results = {
            "total": len(matches),
            "success": 0,
            "failed": 0,
            "failed_matches": []
        }
        
        for match in matches:
            try:
                match_id = self.load_full_match_data(match)
                if match_id:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    results["failed_matches"].append({
                        "external_id": getattr(match, 'external_id', None),
                        "reason": "load_full_match_data returned None"
                    })
            except Exception as e:
                results["failed"] += 1
                results["failed_matches"].append({
                    "external_id": getattr(match, 'external_id', None),
                    "reason": str(e)
                })
                logger.error("Error in bulk_load_matches", extra={
                    "match_external_id": getattr(match, 'external_id', None),
                    "error": str(e)
                }, exc_info=True)
        
        logger.info("Bulk load completed", extra=results)
        return results