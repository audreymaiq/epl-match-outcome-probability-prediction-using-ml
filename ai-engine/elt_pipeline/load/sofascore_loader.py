# elt_pipeline/load/sofascore_loader.py

"""
SofaScore ETL Pipeline: Loader - Ghi các đối tượng đã chuẩn hóa vào database.

"""

import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text

from elt_pipeline.transform.data_structures import (
    ParsedMatch, ParsedTeam, ParsedStadium, ParsedReferee, ParsedLeague, ParsedSeason, ParsedPlayer, ParsedMatchEvent
)
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
            self.session.execute(text("SELECT 1"))
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
        
        column_str = ", ".join([f'"{col}"' for col in columns])
        column_placeholders = ", ".join([f":{col}" for col in columns])
        # Lọc ra các cột không phải là một phần của khóa xung đột để cập nhật
        update_columns = [col for col in columns if col not in conflict_columns]
        update_sets = ", ".join([f'"{col}" = EXCLUDED."{col}"' for col in update_columns])
        conflict_cols = ", ".join([f'"{col}"' for col in conflict_columns])
        
        # Chỉ thực hiện UPDATE nếu có cột cần cập nhật
        do_update_clause = f"DO UPDATE SET {update_sets}" if update_sets else "DO NOTHING"

        query = f'''
            INSERT INTO "{table_name}" ({column_str}) 
            VALUES ({column_placeholders})
            ON CONFLICT ({conflict_cols}) 
            {do_update_clause}
            RETURNING id;
        '''
        return query

    def upsert_league(self, league: ParsedLeague) -> Optional[int]:
        """Upsert một giải đấu và cập nhật internal_id của nó."""
        if not league: return None
        try:
            if league.internal_id: return league.internal_id

            table_config = self._get_table_config("Leagues")
            query = self._build_upsert_query(table_config)
            params = {
                "name": league.name, 
                "country": league.country,
                "established_year": league.established_year
            }
            result = self.session.execute(text(query), params)
            league.internal_id = result.scalar_one_or_none()
            if league.internal_id:
                logger.debug(f"Upserted League: {league.name} (ID: {league.internal_id})")
            return league.internal_id
        except Exception:
            logger.error(f"Failed to upsert league: {league.name}", exc_info=True)
            raise

    def upsert_season(self, season: ParsedSeason) -> Optional[int]:
        """Upsert một mùa giải và cập nhật internal_id của nó."""
        if not season: return None
        try:
            if season.internal_id: return season.internal_id

            league_id = self.upsert_league(season.league)
            if not league_id: raise ValueError(f"Could not get ID for league: {season.league.name}")

            table_config = self._get_table_config("Seasons")
            query = self._build_upsert_query(table_config)
            params = {
                "league_id": league_id,
                "start_year": season.start_year,
                "end_year": season.end_year,
                "name": season.name
            }
            result = self.session.execute(text(query), params)
            season.internal_id = result.scalar_one_or_none()
            if season.internal_id:
                logger.debug(f"Upserted Season: {season.name} (ID: {season.internal_id})")
            return season.internal_id
        except Exception:
            logger.error(f"Failed to upsert season: {season.name}", exc_info=True)
            raise

    def upsert_stadium(self, stadium: ParsedStadium) -> Optional[int]:
        """Upsert một sân vận động và cập nhật internal_id của nó."""
        if not stadium: return None
        try:
            if stadium.internal_id: return stadium.internal_id

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
                logger.debug(f"Upserted stadium: {stadium.name} (ID: {stadium.internal_id})")
            return stadium.internal_id
        except Exception:
            logger.error(f"Error upserting stadium: {getattr(stadium, 'name', None)}", exc_info=True)
            raise

    def upsert_team(self, team: ParsedTeam) -> Optional[int]:
        """Upsert một đội bóng, ghi đầy đủ dữ liệu, và tạo mapping."""
        if not team: return None
        try:
            if team.internal_id: return team.internal_id

            # Kiểm tra mapping trước
            internal_id = get_internal_id(str(team.external_id), "team", "sofascore", self.session)
            if internal_id:
                team.internal_id = internal_id
                return internal_id

            # Upsert các thực thể phụ thuộc
            stadium_id = self.upsert_stadium(team.stadium) if team.stadium else None

            table_config = self._get_table_config("Teams")
            query = self._build_upsert_query(table_config)
            params = {
                "name": team.name,
                "short_name": team.short_name,
                "stadium_id": stadium_id,
                "established_year": team.established_year,
                "logo_url": team.logo_url
            }
            result = self.session.execute(text(query), params)
            team.internal_id = result.scalar_one_or_none()

            if team.internal_id:
                upsert_mapping(str(team.external_id), team.internal_id, "team", "sofascore", self.session)
                logger.debug(f"Upserted Team: {team.name} (ID: {team.internal_id})")
            return team.internal_id
        except Exception:
            logger.error(f"Failed in upsert_team: {getattr(team, 'name', None)}", exc_info=True)
            raise

    def upsert_referee(self, referee: ParsedReferee) -> Optional[int]:
        """Upsert một trọng tài, ghi đầy đủ dữ liệu, và tạo mapping."""
        if not referee: return None
        try:
            if referee.internal_id: return referee.internal_id

            internal_id = get_internal_id(str(referee.external_id), "referee", "sofascore", self.session)
            if internal_id:
                referee.internal_id = internal_id
                return internal_id

            table_config = self._get_table_config("Referees")
            query = self._build_upsert_query(table_config)
            params = {
                "name": referee.name,
                "date_of_birth": referee.date_of_birth,
                "country": referee.country
            }
            result = self.session.execute(text(query), params)
            referee.internal_id = result.scalar_one_or_none()

            if referee.internal_id:
                upsert_mapping(str(referee.external_id), referee.internal_id, "referee", "sofascore", self.session)
                logger.debug(f"Upserted Referee: {referee.name} (ID: {referee.internal_id})")
            return referee.internal_id
        except Exception:
            logger.error(f"Failed in upsert_referee: {getattr(referee, 'name', None)}", exc_info=True)
            raise

    def upsert_player(self, player: ParsedPlayer) -> Optional[int]:
        """Upsert một cầu thủ, ghi đầy đủ dữ liệu, và tạo mapping."""
        if not player: return None
        try:
            if player.internal_id: return player.internal_id

            internal_id = get_internal_id(str(player.external_id), "player", "sofascore", self.session)
            if internal_id:
                player.internal_id = internal_id
                return internal_id

            table_config = self._get_table_config("Players")
            query = self._build_upsert_query(table_config)
            params = {
                "name": player.name,
                "position": player.position,
                "date_of_birth": player.date_of_birth,
                "nationality": player.nationality,
                "height": player.height
            }
            result = self.session.execute(text(query), params)
            player.internal_id = result.scalar_one_or_none()

            if player.internal_id:
                upsert_mapping(str(player.external_id), player.internal_id, "player", "sofascore", self.session)
                logger.debug(f"Upserted Player: {player.name} (ID: {player.internal_id})")
            return player.internal_id
        except Exception:
            logger.error(f"Failed in upsert_player: {getattr(player, 'name', None)}", exc_info=True)
            raise

    def upsert_match(self, match: ParsedMatch) -> Optional[int]:
        """Upserts a single match record."""
        try:
            internal_id = get_internal_id(str(match.external_id), "match", "sofascore", self.session)
            if internal_id:
                logger.debug(f"Match mapping exists, skipping upsert. ExtID: {match.external_id}")
                match.internal_id = internal_id
                return internal_id
            
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
            
            if not all([match.home_team.internal_id, match.away_team.internal_id, match.season.internal_id]):
                raise ValueError("Missing internal IDs for team or season.")

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
                "status": match.status,
                "outcome": match.outcome if match.status == 'FINISHED' else None
            }
            
            result = self.session.execute(query, params)
            match.internal_id = result.scalar_one_or_none()
            
            if match.internal_id:
                upsert_mapping(str(match.external_id), match.internal_id, "match", "sofascore", self.session)
                logger.debug(f"Upserted Match: ExtID {match.external_id}, IntID {match.internal_id}")
                return match.internal_id
            return None
                    
        except Exception:
            logger.error(f"Failed to upsert match: ExtID {getattr(match, 'external_id', None)}", exc_info=True)
            raise
    
    def upsert_match_event(self, event: ParsedMatchEvent, match_internal_id: int):
        """Inserts a single match event record. This is a simple INSERT, not an upsert."""
        if not event or not match_internal_id:
            return
        try:
            # Upsert các thực thể liên quan
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
                "description": event.description
            }
            self.session.execute(query, params)
        except Exception:
            logger.error(f"Failed to insert match event for match_id {match_internal_id}", exc_info=True)
        
    def load_full_match_data(self, match: ParsedMatch) -> Optional[int]:
        """Điều phối việc tải một trận đấu hoàn chỉnh và các thực thể liên quan của nó."""
        try:
            self.upsert_season(match.season)
            self.upsert_team(match.home_team)
            self.upsert_team(match.away_team)
            self.upsert_stadium(match.stadium)
            self.upsert_referee(match.referee)
            
            match_id = self.upsert_match(match)
            
            if match_id and match.events:
                # Xóa các sự kiện cũ để tránh trùng lặp nếu chạy lại
                self.session.execute(text('DELETE FROM "MatchEvents" WHERE match_id = :mid'), {"mid": match_id})
                for event in match.events:
                    self.upsert_match_event(event, match_id)

            if match_id:
                logger.info(f"Successfully loaded complete match data: ExtID {match.external_id}, IntID {match_id}")
            return match_id
                    
        except Exception:
            logger.error(f"Error during full match data loading: ExtID {getattr(match, 'external_id', None)}", exc_info=True)
            raise

    def bulk_load_matches(self, matches: List[ParsedMatch]) -> Dict[str, Any]:
        """Tải hàng loạt các trận đấu với theo dõi lỗi chi tiết."""
        results = {"total": len(matches), "success": 0, "failed": 0, "failed_matches": []}
        for match in matches:
            try:
                match_id = self.load_full_match_data(match)
                if match_id:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    results["failed_matches"].append({ "external_id": match.external_id, "reason": "Loader returned None"})
            except Exception as e:
                results["failed"] += 1
                results["failed_matches"].append({ "external_id": match.external_id, "reason": str(e)})
                # Không log lỗi ở đây nữa vì nó đã được log ở các hàm con
        
        logger.info("Bulk load completed", extra=results)
        return results