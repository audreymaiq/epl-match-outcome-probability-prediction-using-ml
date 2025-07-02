# # elt_pipeline/load/sofascore_loader.py

# """
# SofaScore ETL Pipeline: Loader - FINAL REVIEWED VERSION
# """

# import logging
# from typing import Optional, Dict, Any, List
# from sqlalchemy.orm import Session
# from sqlalchemy.exc import SQLAlchemyError
# from sqlalchemy import text, JSON
# from contextlib import contextmanager

# from elt_pipeline.transform.data_structures import (
#     ParsedMatch, ParsedTeam, ParsedStadium, ParsedReferee, ParsedLeague, ParsedSeason, ParsedPlayer, ParsedMatchEvent
# )
# from config.core_constants import MatchStatus
# from utils.external_mapping import get_internal_id, upsert_mapping

# logger = logging.getLogger(__name__)

# class LoaderError(Exception):
#     """Custom exception for loader errors."""
#     pass

# class SofaScoreLoader:
#     def __init__(self, session: Session):
#         self.session = session
#         self._validate_session()
#         self._entity_cache: Dict[str, int] = {}

#     def _validate_session(self):
#         if not self.session: raise ValueError("Database session is required")
#         try:
#             self.session.execute(text("SELECT 1"))
#         except Exception as e:
#             logger.error(f"Database session validation failed: {e}")
#             raise LoaderError(f"Invalid database session: {e}")

#     @contextmanager
#     def _transaction_context(self):
#         if self.session.in_transaction():
#             yield
#             return
#         try:
#             with self.session.begin_nested(): yield
#         except Exception as e:
#             logger.error(f"Transaction block failed: {e}")
#             raise

#     def _get_cache_key(self, entity_type: str, external_id: Any) -> str:
#         return f"{entity_type}:{external_id}"

#     def _cache_entity(self, entity_type: str, external_id: Any, internal_id: int):
#         if not external_id or not internal_id: return
#         self._entity_cache[self._get_cache_key(entity_type, external_id)] = internal_id
        
#     def _find_internal_id(self, entity_type: str, external_id: Any) -> Optional[int]:
#         if not external_id: return None
#         cached_id = self._entity_cache.get(self._get_cache_key(entity_type, external_id))
#         if cached_id: return cached_id
#         internal_id = get_internal_id(str(external_id), entity_type, "sofascore", self.session)
#         if internal_id:
#             self._cache_entity(entity_type, external_id, internal_id)
#             return internal_id
#         return None

#     def upsert_league(self, league: ParsedLeague) -> Optional[int]:
#         if not league or not league.external_id: return None
#         try:
#             if league.internal_id: return league.internal_id
#             internal_id = self._find_internal_id("league", league.external_id)
#             if internal_id: league.internal_id = internal_id; return internal_id
            
#             # UNIQUE constraint trong DB là trên (name)
#             query = text("""
#                 INSERT INTO "Leagues" (name, country)
#                 VALUES (:name, :country)
#                 ON CONFLICT (name) DO UPDATE SET
#                     country = EXCLUDED.country,
#                     -- Không update các trường khác vì chúng có thể không được cung cấp
#                     updated_at = NOW()
#                 RETURNING id;
#             """)
#             params = {"name": league.name.strip(), "country": league.country.strip() if league.country else "Unknown"}
#             result = self.session.execute(query, params).scalar_one()
#             league.internal_id = result
            
#             upsert_mapping(str(league.external_id), league.internal_id, "league", "sofascore", session=self.session)
#             self._cache_entity("league", league.external_id, league.internal_id)
#             return league.internal_id
#         except Exception as e:
#             logger.error(f"Error upserting league '{getattr(league, 'name', 'Unknown')}': {e}", exc_info=True)
#             raise LoaderError(f"Failed to upsert league: {e}")

#     def upsert_season(self, season: ParsedSeason) -> Optional[int]:
#         if not season or not season.external_id: return None
#         try:
#             if season.internal_id: return season.internal_id
#             internal_id = self._find_internal_id("season", season.external_id)
#             if internal_id: season.internal_id = internal_id; return internal_id
            
#             league_id = self.upsert_league(season.league)
#             if not league_id: raise LoaderError(f"Could not get ID for league: {season.league.name}")
            
#             # UNIQUE constraint trong DB là trên (league_id, name)
#             query = text("""
#                 INSERT INTO "Seasons" (league_id, start_year, end_year, name)
#                 VALUES (:league_id, :start_year, :end_year, :name)
#                 ON CONFLICT (league_id, name) DO NOTHING RETURNING id;
#             """)
#             params = {"league_id": league_id, "start_year": season.start_year, "end_year": season.end_year, "name": season.name.strip()}
#             result = self.session.execute(query, params).scalar_one_or_none()
            
#             if not result:
#                 # Nếu CONFLICT xảy ra, ID không được trả về, ta phải SELECT lại để lấy ID của record đã tồn tại
#                 find_query = text('SELECT id FROM "Seasons" WHERE league_id = :league_id AND name = :name')
#                 result = self.session.execute(find_query, params).scalar_one()
                
#             season.internal_id = result
#             upsert_mapping(str(season.external_id), season.internal_id, "season", "sofascore", session=self.session)
#             self._cache_entity("season", season.external_id, season.internal_id)
#             return season.internal_id
#         except Exception as e:
#             logger.error(f"Error upserting season '{getattr(season, 'name', 'Unknown')}': {e}", exc_info=True)
#             raise LoaderError(f"Failed to upsert season: {e}")

#     def upsert_stadium(self, stadium: ParsedStadium) -> Optional[int]:
#         if not stadium or not stadium.external_id or not stadium.name: return None
#         try:
#             if stadium.internal_id: return stadium.internal_id
#             internal_id = self._find_internal_id("stadium", stadium.external_id)
#             if internal_id: stadium.internal_id = internal_id; return internal_id

#             # UNIQUE constraint trong DB là trên (name)
#             query = text("""
#                 INSERT INTO "Stadiums" (name, city, capacity)
#                 VALUES (:name, :city, :capacity)
#                 ON CONFLICT (name) DO UPDATE SET
#                     city = COALESCE(EXCLUDED.city, "Stadiums".city),
#                     capacity = COALESCE(EXCLUDED.capacity, "Stadiums".capacity),
#                     updated_at = NOW()
#                 RETURNING id;
#             """)
#             params = {
#                 "name": stadium.name.strip(), 
#                 "city": stadium.city.strip() if stadium.city else None, 
#                 "capacity": stadium.capacity
#             }
#             result = self.session.execute(query, params).scalar_one()
#             stadium.internal_id = result
            
#             upsert_mapping(str(stadium.external_id), stadium.internal_id, "stadium", "sofascore", session=self.session)
#             self._cache_entity("stadium", stadium.external_id, stadium.internal_id)
#             return stadium.internal_id
#         except Exception as e:
#             logger.error(f"Error upserting stadium '{getattr(stadium, 'name', 'Unknown')}': {e}", exc_info=True)
#             raise LoaderError(f"Failed to upsert stadium: {e}")

#     def upsert_team(self, team: ParsedTeam) -> Optional[int]:
#         if not team or not team.external_id: return None
#         try:
#             if team.internal_id: return team.internal_id
#             internal_id = self._find_internal_id("team", team.external_id)
#             if internal_id: team.internal_id = internal_id; return internal_id
            
#             stadium_id = self.upsert_stadium(team.stadium) if team.stadium else None
            
#             # UNIQUE constraint trong DB là trên (name)
#             query = text("""
#                 INSERT INTO "Teams" (name, short_name, stadium_id, established_year, logo_url)
#                 VALUES (:name, :short_name, :stadium_id, :established_year, :logo_url)
#                 ON CONFLICT (name) DO UPDATE SET
#                     short_name = COALESCE(EXCLUDED.short_name, "Teams".short_name),
#                     stadium_id = COALESCE(EXCLUDED.stadium_id, "Teams".stadium_id),
#                     established_year = COALESCE(EXCLUDED.established_year, "Teams".established_year),
#                     logo_url = COALESCE(EXCLUDED.logo_url, "Teams".logo_url),
#                     updated_at = NOW()
#                 RETURNING id;
#             """)
#             params = {
#                 "name": team.name.strip(), 
#                 "short_name": team.short_name.strip() if team.short_name else None, 
#                 "stadium_id": stadium_id, 
#                 "established_year": team.established_year, 
#                 "logo_url": team.logo_url
#             }
#             result = self.session.execute(query, params).scalar_one()
#             team.internal_id = result

#             upsert_mapping(str(team.external_id), team.internal_id, "team", "sofascore", session=self.session)
#             self._cache_entity("team", team.external_id, team.internal_id)
#             return team.internal_id
#         except Exception as e:
#             logger.error(f"Error upserting team '{getattr(team, 'name', 'Unknown')}': {e}", exc_info=True)
#             raise LoaderError(f"Failed to upsert team: {e}")

#     def upsert_referee(self, referee: ParsedReferee) -> Optional[int]:
#         if not referee or not referee.external_id or not referee.name: return None
#         try:
#             if referee.internal_id: return referee.internal_id
#             internal_id = self._find_internal_id("referee", referee.external_id)
#             if internal_id: referee.internal_id = internal_id; return internal_id
            
#             query = text("""
#                 INSERT INTO "Referees" (name, country)
#                 VALUES (:name, :country)
#                 ON CONFLICT (name) DO UPDATE SET
#                     country = EXCLUDED.country,
#                     updated_at = NOW()
#                 RETURNING id;
#             """)
#             params = {"name": referee.name.strip(), "country": referee.country.strip() if referee.country else None}
#             result = self.session.execute(query, params).scalar_one()
#             referee.internal_id = result
            
#             upsert_mapping(str(referee.external_id), referee.internal_id, "referee", "sofascore", session=self.session)
#             self._cache_entity("referee", referee.external_id, referee.internal_id)
#             return referee.internal_id
#         except Exception as e:
#             logger.error(f"Error upserting referee '{getattr(referee, 'name', 'Unknown')}': {e}", exc_info=True)
#             raise LoaderError(f"Failed to upsert referee: {e}")

#     def upsert_player(self, player: ParsedPlayer) -> Optional[int]:
#         # SỬA 3: Logic UPSERT cho cầu thủ, yêu cầu UNIQUE INDEX trên (name, date_of_birth)
#         # Bạn cần thêm: CREATE UNIQUE INDEX uq_player_name_dob ON "Players" (name, date_of_birth);
#         if not player or not player.external_id or not player.name: return None
#         try:
#             if player.internal_id: return player.internal_id
#             internal_id = self._find_internal_id("player", player.external_id)
#             if internal_id: player.internal_id = internal_id; return internal_id
            
#             query = text("""
#                 INSERT INTO "Players" (name, "position", date_of_birth, nationality)
#                 VALUES (:name, :position, :date_of_birth, :nationality)
#                 ON CONFLICT (name, date_of_birth) DO UPDATE SET
#                     "position" = EXCLUDED."position",
#                     nationality = EXCLUDED.nationality,
#                     updated_at = NOW()
#                 RETURNING id;
#             """)
#             # ParsedPlayer.position đã là Enum, ta lấy .value
#             params = {
#                 "name": player.name.strip(), 
#                 "position": player.position.value if player.position else None, 
#                 "date_of_birth": player.date_of_birth, 
#                 "nationality": player.nationality.strip() if player.nationality else None
#             }
#             result = self.session.execute(query, params).scalar_one()
#             player.internal_id = result
            
#             upsert_mapping(str(player.external_id), player.internal_id, "player", "sofascore", session=self.session)
#             self._cache_entity("player", player.external_id, player.internal_id)
#             return player.internal_id
#         except Exception as e:
#             logger.error(f"Error upserting player '{getattr(player, 'name', 'Unknown')}': {e}", exc_info=True)
#             raise LoaderError(f"Failed to upsert player: {e}")

#     def upsert_match(self, match: ParsedMatch) -> Optional[int]:
#         if not match or not match.external_id: return None
#         try:
#             # Lấy các ID phụ thuộc trước
#             home_team_id = self.upsert_team(match.home_team)
#             away_team_id = self.upsert_team(match.away_team)
#             season_id = self.upsert_season(match.season)
#             stadium_id = self.upsert_stadium(match.stadium) if match.stadium else None
#             referee_id = self.upsert_referee(match.referee) if match.referee else None

#             if not all([home_team_id, away_team_id, season_id]):
#                 raise LoaderError("Missing required internal IDs for teams or season.")

#             # UNIQUE constraint trong DB là (match_datetime, home_team_id, away_team_id)
#             query = text('''
#                 INSERT INTO "Matches" (
#                     season_id, match_datetime, match_week, home_team_id, away_team_id, stadium_id, referee_id, 
#                     status, home_goals, away_goals, outcome, half_time_home_goals, half_time_away_goals
#                 )
#                 VALUES (
#                     :season_id, :dt, :mw, :h_id, :a_id, :st_id, :ref_id, 
#                     :status, :hg, :ag, :outcome, :hthg, :htag
#                 )
#                 ON CONFLICT (match_datetime, home_team_id, away_team_id) DO UPDATE SET
#                     status = EXCLUDED.status,
#                     home_goals = EXCLUDED.home_goals,
#                     away_goals = EXCLUDED.away_goals,
#                     outcome = EXCLUDED.outcome,
#                     half_time_home_goals = EXCLUDED.half_time_home_goals,
#                     half_time_away_goals = EXCLUDED.half_time_away_goals,
#                     stadium_id = EXCLUDED.stadium_id,
#                     referee_id = EXCLUDED.referee_id,
#                     updated_at = NOW()
#                 RETURNING id;
#             ''')

#             params = {
#                 "season_id": season_id, "dt": match.match_datetime, "mw": match.match_week,
#                 "h_id": home_team_id, "a_id": away_team_id, "st_id": stadium_id, "ref_id": referee_id,
#                 "status": match.status.value, "hg": match.home_goals, "ag": match.away_goals,
#                 "outcome": match.outcome.value if match.outcome else None,
#                 "hthg": match.half_time_home_goals, "htag": match.half_time_away_goals
#             }
            
#             result = self.session.execute(query, params).scalar_one()
#             match.internal_id = result
            
#             upsert_mapping(str(match.external_id), match.internal_id, "match", "sofascore", session=self.session)
#             self._cache_entity("match", match.external_id, match.internal_id)
#             return match.internal_id
#         except Exception as e:
#             logger.error(f"Error upserting match ExtID '{getattr(match, 'external_id', 'Unknown')}': {e}", exc_info=True)
#             raise LoaderError(f"Failed to upsert match: {e}")


#     def insert_new_match(self, match: ParsedMatch) -> Optional[int]:
#         """Chỉ INSERT một trận đấu mới. Được gọi bởi upsert_match."""
#         if not all([match.home_team.internal_id, match.away_team.internal_id, match.season.internal_id]):
#             raise LoaderError("Missing internal IDs for home_team, away_team, or season for new match insert.")
        
#         outcome_value = match.outcome.value if match.outcome and match.status == MatchStatus.FINISHED else None
        
#         # Câu lệnh INSERT không cần ON CONFLICT vì ta đã kiểm tra trước
#         query = text('''
#             INSERT INTO "Matches" (season_id, match_datetime, match_week, home_team_id, away_team_id, stadium_id, referee_id, status, status_label, home_goals, away_goals, outcome, outcome_label, outcome_code,
#                                    half_time_home_goals, half_time_away_goals, second_half_home_goals, second_half_away_goals, home_goals_normaltime, away_goals_normaltime,
#                                    injury_time_first_half, injury_time_second_half, attendance, importance, has_xg, has_event_player_statistics)
#             VALUES (:season_id, :dt, :match_week, :h_id, :a_id, :st_id, :ref_id, :status, :status_label, :hg, :ag, :outcome, :outcome_label, :outcome_code,
#                     :hthg, :htag, :shhg, :shag, :hg_normal, :ag_normal, :it1, :it2, :attendance, :importance, :has_xg, :has_events)
#             RETURNING id;
#         ''')
#         params = {"season_id": match.season.internal_id, "dt": match.match_datetime, "match_week": match.match_week, "h_id": match.home_team.internal_id, "a_id": match.away_team.internal_id, "st_id": match.stadium.internal_id if match.stadium else None, "ref_id": match.referee.internal_id if match.referee else None, "status": match.status.value, "status_label": match.status_label, "hg": match.home_goals, "ag": match.away_goals, "outcome": outcome_value, "outcome_label": match.outcome_label, "outcome_code": match.outcome_code, "hthg": match.half_time_home_goals, "htag": match.half_time_away_goals, "shhg": match.second_half_home_goals, "shag": match.second_half_away_goals, "hg_normal": match.home_goals_normaltime, "ag_normal": match.away_goals_normaltime, "it1": match.injury_time_first_half, "it2": match.injury_time_second_half, "attendance": match.attendance, "importance": match.importance, "has_xg": match.has_xg, "has_events": match.has_event_player_statistics}
        
#         result = self.session.execute(query, params).scalar_one_or_none()
#         match.internal_id = result
#         if match.internal_id:
#             upsert_mapping(str(match.external_id), match.internal_id, "match", "sofascore", session=self.session)
#             self._cache_entity("match", match.external_id, match.internal_id)
#         return match.internal_id

#     def update_existing_match(self, match: ParsedMatch) -> Optional[int]:
#         """Chỉ UPDATE một trận đấu đã tồn tại. Được gọi bởi upsert_match."""
#         if not match.internal_id: return None
        
#         outcome_value = match.outcome.value if match.outcome and match.status == MatchStatus.FINISHED else None
        
#         query = text('''
#             UPDATE "Matches" SET
#                 status = :status, status_label = :status_label, home_goals = :hg, away_goals = :ag, outcome = :outcome, outcome_label = :outcome_label, outcome_code = :outcome_code,
#                 half_time_home_goals = :hthg, half_time_away_goals = :htag, second_half_home_goals = :shhg, second_half_away_goals = :shag,
#                 home_goals_normaltime = :hg_normal, away_goals_normaltime = :ag_normal, injury_time_first_half = :it1, injury_time_second_half = :it2,
#                 attendance = :attendance, importance = :importance, has_xg = :has_xg, has_event_player_statistics = :has_events,
#                 referee_id = :ref_id, stadium_id = :st_id, updated_at = NOW()
#             WHERE id = :match_id;
#         ''')
#         params = {"match_id": match.internal_id, "st_id": match.stadium.internal_id if match.stadium else None, "ref_id": match.referee.internal_id if match.referee else None, "status": match.status.value, "status_label": match.status_label, "hg": match.home_goals, "ag": match.away_goals, "outcome": outcome_value, "outcome_label": match.outcome_label, "outcome_code": match.outcome_code, "hthg": match.half_time_home_goals, "htag": match.half_time_away_goals, "shhg": match.second_half_home_goals, "shag": match.second_half_away_goals, "hg_normal": match.home_goals_normaltime, "ag_normal": match.away_goals_normaltime, "it1": match.injury_time_first_half, "it2": match.injury_time_second_half, "attendance": match.attendance, "importance": match.importance, "has_xg": match.has_xg, "has_events": match.has_event_player_statistics}
        
#         self.session.execute(query, params)
#         return match.internal_id

#     def upsert_match_events(self, events: List[ParsedMatchEvent], match_internal_id: int):
#         if not events or not match_internal_id: return
#         try:
#             self.session.execute(text('DELETE FROM "MatchEvents" WHERE match_id = :mid'), {"mid": match_internal_id})
#             events_to_insert = []
#             for event in events:
#                 team_id = self.upsert_team(event.team) if event.team else None
#                 player_id = self.upsert_player(event.player) if event.player else None
#                 related_player_id = self.upsert_player(event.related_player) if event.related_player else None
#                 events_to_insert.append({"match_id": match_internal_id, "minute": event.minute, "event_type": event.event_type.value, "team_id": team_id, "player_id": player_id, "related_player_id": related_player_id, "period": event.period.value, "description": event.description[:500] if event.description else None, "raw_event_data": event.raw_event_data})
#             if not events_to_insert: return
#             query = text('''INSERT INTO "MatchEvents" (match_id, minute, event_type, team_id, player_id, related_player_id, period, description, raw_event_data)
#                             VALUES (:match_id, :minute, :event_type, :team_id, :player_id, :related_player_id, :period, :description, :raw_event_data)''')
#             self.session.execute(query, events_to_insert)
#         except Exception as e:
#             logger.error(f"Failed to bulk insert match events for match_id {match_internal_id}: {e}", exc_info=True)
#             raise LoaderError(f"Failed to insert match events: {e}")
        
#     def load_full_match_data(self, match: ParsedMatch) -> Optional[int]:
#         if not match: return None
#         logger.debug(f"Starting to load full data for match ExtID: {match.external_id}")
#         try:
#             with self.session.begin():
#                 self.upsert_season(match.season)
#                 self.upsert_team(match.home_team)
#                 self.upsert_team(match.away_team)
#                 self.upsert_stadium(match.stadium)
#                 self.upsert_referee(match.referee)
#                 match_id = self.upsert_match(match)
#                 if match_id and match.events:
#                     self.upsert_match_events(match.events, match_id)
#                 if match_id:
#                     logger.info(f"Successfully loaded complete match data: ExtID {match.external_id} -> IntID {match_id}")
#                 return match_id
#         except Exception as e:
#             logger.error(f"Full load failed for match ExtID {getattr(match, 'external_id', 'Unknown')}. Transaction rolled back. Error: {e}", exc_info=True)
#             raise LoaderError(f"Failed to fully load match data: {e}")

#     def bulk_load_matches(self, matches: List[ParsedMatch]) -> Dict[str, Any]:
#         if not matches: return {"total": 0, "success": 0, "failed": 0, "failed_matches": []}
#         results = {"total": len(matches), "success": 0, "failed": 0, "failed_matches": []}
#         logger.info(f"Starting bulk load of {len(matches)} matches")
#         for i, match in enumerate(matches):
#             try:
#                 match_id = self.load_full_match_data(match)
#                 if match_id:
#                     results["success"] += 1
#                 else:
#                     results["failed"] += 1
#                     results["failed_matches"].append({"external_id": getattr(match, 'external_id', f'index_{i}'), "reason": "Loader returned None without raising an exception."})
#             except LoaderError as e:
#                 results["failed"] += 1
#                 results["failed_matches"].append({"external_id": getattr(match, 'external_id', f'index_{i}'), "reason": str(e)})
#             except Exception as e:
#                 results["failed"] += 1
#                 results["failed_matches"].append({"external_id": getattr(match, 'external_id', f'index_{i}'), "reason": f"An unexpected error occurred: {str(e)}"})
#                 logger.error(f"Unexpected fatal error in bulk load for match {i}: {e}", exc_info=True)
#         self.clear_cache()
#         logger.info("Bulk load completed.", extra=results)
#         return results

#     def clear_cache(self):
#         self._entity_cache.clear()
#         logger.debug("Entity cache cleared")

# elt_pipeline/load/sofascore_loader.py

import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text, exc

from elt_pipeline.transform.data_structures import (
    ParsedMatch, ParsedTeam, ParsedStadium, ParsedReferee, ParsedLeague, ParsedSeason, ParsedPlayer, ParsedMatchEvent
)
from utils.external_mapping import get_internal_id, upsert_mapping

logger = logging.getLogger(__name__)
SOURCE_SYSTEM = "sofascore"

class LoaderError(Exception):
    """Custom exception for loader-specific errors."""
    pass

class SofaScoreLoader:
    """
    Tải dữ liệu đã được biến đổi (Parsed*) vào cơ sở dữ liệu.
    Sử dụng chiến lược UPSERT (ON CONFLICT) hiệu suất cao và cache trong bộ nhớ.
    """

    def __init__(self, session: Session):
        """
        Khởi tạo Loader với một session SQLAlchemy.
        Args:
            session: Một session SQLAlchemy đã được khởi tạo.
        """
        if not session:
            raise ValueError("Database session is required for the loader.")
        self.session = session
        # Cache để lưu mapping từ external_id -> internal_id trong một lần chạy
        # Giảm thiểu đáng kể các truy vấn DB lặp lại.
        self._entity_cache: Dict[str, int] = {}
        logger.info("SofaScoreLoader initialized with an active session.")

    def _get_cache_key(self, entity_type: str, external_id: Any) -> str:
        """Tạo một khóa cache duy nhất cho một thực thể."""
        return f"{entity_type}:{external_id}"

    def _find_internal_id(self, entity_type: str, external_id: Any) -> Optional[int]:
        """
TÌm internal_id bằng cách kiểm tra cache trước, sau đó mới truy vấn DB."""
        if not external_id:
            return None
        
        cache_key = self._get_cache_key(entity_type, external_id)
        if cache_key in self._entity_cache:
            return self._entity_cache[cache_key]
        
        internal_id = get_internal_id(str(external_id), entity_type, SOURCE_SYSTEM, self.session)
        if internal_id:
            self._entity_cache[cache_key] = internal_id
            return internal_id
            
        return None

    def _upsert_entity(
        self,
        parsed_obj: Any,
        entity_type: str,
        unique_constraint_cols: List[str],
        sql_query: str,
        params: Dict[str, Any]
    ) -> Optional[int]:
        """
        Hàm helper chung để thực hiện logic UPSERT cho các thực thể.
        """
        if not parsed_obj or not getattr(parsed_obj, 'external_id', None):
            return None
        
        # Nếu object đã có internal_id (từ lần xử lý trước), trả về ngay
        if getattr(parsed_obj, 'internal_id', None):
            return parsed_obj.internal_id

        # Kiểm tra cache và DB
        internal_id = self._find_internal_id(entity_type, parsed_obj.external_id)
        if internal_id:
            parsed_obj.internal_id = internal_id
            return internal_id

        try:
            # Thực hiện câu lệnh UPSERT
            result = self.session.execute(text(sql_query), params).scalar_one_or_none()
            
            # Nếu ON CONFLICT xảy ra và không có RETURNING, phải SELECT lại
            if not result:
                find_conditions = " AND ".join([f'"{col}" = :{col}' for col in unique_constraint_cols])
                find_query = text(f'SELECT id FROM "{entity_type.capitalize()}s" WHERE {find_conditions}')
                result = self.session.execute(find_query, params).scalar_one()

            internal_id = result
            parsed_obj.internal_id = internal_id
            
            # Cập nhật bảng mapping và cache
            upsert_mapping(str(parsed_obj.external_id), internal_id, entity_type, SOURCE_SYSTEM, session=self.session)
            self._entity_cache[self._get_cache_key(entity_type, parsed_obj.external_id)] = internal_id
            
            return internal_id
        except exc.SQLAlchemyError as e:
            logger.error(f"Error upserting {entity_type} '{getattr(parsed_obj, 'name', 'Unknown')}': {e}", exc_info=True)
            raise LoaderError(f"Failed to upsert {entity_type}: {e}")

    # --- Các hàm Upsert cho từng loại thực thể ---

    def _upsert_league(self, league: ParsedLeague) -> Optional[int]:
        # YÊU CẦU DB: CREATE UNIQUE INDEX uq_leagues_name ON "Leagues" (name);
        query = """
            INSERT INTO "Leagues" (name, country, unique_tournament_id, priority)
            VALUES (:name, :country, :unique_tournament_id, :priority)
            ON CONFLICT (name) DO UPDATE SET
                country = EXCLUDED.country,
                updated_at = NOW()
            RETURNING id;
        """
        params = {
            "name": league.name, "country": league.country,
            "unique_tournament_id": league.unique_tournament_id, "priority": league.priority
        }
        return self._upsert_entity(league, "league", ["name"], query, params)
        
    def _upsert_season(self, season: ParsedSeason) -> Optional[int]:
        # YÊU CẦU DB: CREATE UNIQUE INDEX uq_seasons_league_name ON "Seasons" (league_id, name);
        league_id = self._upsert_league(season.league)
        if not league_id: raise LoaderError(f"Could not get ID for league: {season.league.name}")

        query = """
            INSERT INTO "Seasons" (league_id, name, start_year, end_year)
            VALUES (:league_id, :name, :start_year, :end_year)
            ON CONFLICT (league_id, name) DO NOTHING RETURNING id;
        """
        params = {
            "league_id": league_id, "name": season.name,
            "start_year": season.start_year, "end_year": season.end_year
        }
        return self._upsert_entity(season, "season", ["league_id", "name"], query, params)
        
    def _upsert_stadium(self, stadium: ParsedStadium) -> Optional[int]:
        # YÊU CẦU DB: CREATE UNIQUE INDEX uq_stadiums_name ON "Stadiums" (name);
        query = """
            INSERT INTO "Stadiums" (name, city, capacity, latitude, longitude)
            VALUES (:name, :city, :capacity, :latitude, :longitude)
            ON CONFLICT (name) DO UPDATE SET
                city = COALESCE(EXCLUDED.city, "Stadiums".city),
                capacity = COALESCE(EXCLUDED.capacity, "Stadiums".capacity),
                updated_at = NOW()
            RETURNING id;
        """
        params = {
            "name": stadium.name, "city": stadium.city, "capacity": stadium.capacity,
            "latitude": stadium.latitude, "longitude": stadium.longitude
        }
        return self._upsert_entity(stadium, "stadium", ["name"], query, params)

    def _upsert_team(self, team: ParsedTeam) -> Optional[int]:
        # YÊU CẦU DB: CREATE UNIQUE INDEX uq_teams_name ON "Teams" (name);
        stadium_id = self._upsert_stadium(team.stadium) if team.stadium else None

        query = """
            INSERT INTO "Teams" (name, short_name, name_code, stadium_id, established_year, manager_name)
            VALUES (:name, :short_name, :name_code, :stadium_id, :established_year, :manager_name)
            ON CONFLICT (name) DO UPDATE SET
                short_name = COALESCE(EXCLUDED.short_name, "Teams".short_name),
                stadium_id = COALESCE(EXCLUDED.stadium_id, "Teams".stadium_id),
                manager_name = COALESCE(EXCLUDED.manager_name, "Teams".manager_name),
                updated_at = NOW()
            RETURNING id;
        """
        params = {
            "name": team.name, "short_name": team.short_name, "name_code": team.name_code,
            "stadium_id": stadium_id, "established_year": team.established_year,
            "manager_name": team.manager_name
        }
        return self._upsert_entity(team, "team", ["name"], query, params)

    def _upsert_referee(self, referee: ParsedReferee) -> Optional[int]:
        # YÊU CẦU DB: CREATE UNIQUE INDEX uq_referees_name ON "Referees" (name);
        query = """
            INSERT INTO "Referees" (name, country) VALUES (:name, :country)
            ON CONFLICT (name) DO UPDATE SET country = EXCLUDED.country RETURNING id;
        """
        params = {"name": referee.name, "country": referee.country}
        return self._upsert_entity(referee, "referee", ["name"], query, params)

    def _upsert_player(self, player: ParsedPlayer) -> Optional[int]:
        # YÊU CẦU DB: CREATE UNIQUE INDEX uq_players_name_dob ON "Players" (name, date_of_birth);
        query = """
            INSERT INTO "Players" (name, position, date_of_birth, nationality)
            VALUES (:name, :position, :date_of_birth, :nationality)
            ON CONFLICT (name, date_of_birth) DO UPDATE SET
                position = EXCLUDED.position,
                nationality = EXCLUDED.nationality
            RETURNING id;
        """
        params = {
            "name": player.name, "position": player.position.value if player.position else None,
            "date_of_birth": player.date_of_birth, "nationality": player.nationality
        }
        return self._upsert_entity(player, "player", ["name", "date_of_birth"], query, params)
        
    def _upsert_match_events(self, events: List[ParsedMatchEvent], match_internal_id: int):
        if not events: return
        
        self.session.execute(text('DELETE FROM "MatchEvents" WHERE match_id = :mid'), {"mid": match_internal_id})
        
        events_to_insert = []
        for event in events:
            player_id = self._upsert_player(event.player) if event.player else None
            related_player_id = self._upsert_player(event.related_player) if event.related_player else None
            team_id = event.team.internal_id if event.team and event.team.internal_id else None

            events_to_insert.append({
                "match_id": match_internal_id, "minute": event.minute,
                "event_type": event.event_type.value, "period": event.period.value,
                "description": event.description, "player_id": player_id,
                "related_player_id": related_player_id, "team_id": team_id
            })
        
        if events_to_insert:
            query = text("""INSERT INTO "MatchEvents" (match_id, minute, event_type, period, description, player_id, related_player_id, team_id)
                            VALUES (:match_id, :minute, :event_type, :period, :description, :player_id, :related_player_id, :team_id)""")
            self.session.execute(query, events_to_insert)

    def _load_single_match(self, match: ParsedMatch) -> Optional[int]:
        """
        Điều phối việc tải một trận đấu duy nhất và tất cả các thực thể liên quan của nó.
        """
        if not match: return None

        # 1. Tải các thực thể phụ thuộc trước
        home_team_id = self._upsert_team(match.home_team)
        away_team_id = self._upsert_team(match.away_team)
        season_id = self._upsert_season(match.season)
        stadium_id = self._upsert_stadium(match.stadium) if match.stadium else (match.home_team.stadium.internal_id if match.home_team.stadium else None)
        referee_id = self._upsert_referee(match.referee) if match.referee else None

        if not all([home_team_id, away_team_id, season_id]):
            raise LoaderError(f"Could not resolve dependencies for match {match.external_id}")

        # 2. Upsert thực thể chính: Trận đấu
        # YÊU CẦU DB: CREATE UNIQUE INDEX uq_matches_season_teams_dt ON "Matches" (season_id, home_team_id, away_team_id, match_datetime);
        query = """
            INSERT INTO "Matches" (season_id, home_team_id, away_team_id, match_datetime, match_week, stadium_id, referee_id, status, outcome, home_goals, away_goals, half_time_home_goals, half_time_away_goals, importance, status_label, outcome_label)
            VALUES (:season_id, :h_id, :a_id, :dt, :mw, :st_id, :ref_id, :status, :outcome, :hg, :ag, :hthg, :htag, :imp, :stat_lbl, :out_lbl)
            ON CONFLICT (season_id, home_team_id, away_team_id, match_datetime) DO UPDATE SET
                status = EXCLUDED.status, outcome = EXCLUDED.outcome, home_goals = EXCLUDED.home_goals,
                away_goals = EXCLUDED.away_goals, half_time_home_goals = EXCLUDED.half_time_home_goals,
                half_time_away_goals = EXCLUDED.half_time_away_goals, updated_at = NOW()
            RETURNING id;
        """
        params = {
            "season_id": season_id, "h_id": home_team_id, "a_id": away_team_id, "dt": match.match_datetime,
            "mw": match.match_week, "st_id": stadium_id, "ref_id": referee_id,
            "status": match.status.value, "outcome": match.outcome.value if match.outcome else None,
            "hg": match.home_goals, "ag": match.away_goals, "hthg": match.half_time_home_goals,
            "htag": match.half_time_away_goals, "imp": match.importance, "stat_lbl": match.status_label,
            "out_lbl": match.outcome_label
        }
        match_id = self._upsert_entity(match, "match", ["season_id", "home_team_id", "away_team_id", "match_datetime"], query, params)

        # 3. Tải các thực thể con: Sự kiện
        if match_id and match.events:
            self._upsert_match_events(match.events, match_id)
        
        return match_id

    def bulk_load_matches(self, matches: List[ParsedMatch]) -> Dict[str, Any]:
        """
        Điểm vào chính để tải một danh sách các trận đấu. Quản lý transaction và báo cáo kết quả.
        """
        if not matches:
            return {"total": 0, "success": 0, "failed": 0, "failed_ids": []}
            
        results = {"total": len(matches), "success": 0, "failed": 0, "failed_ids": []}
        logger.info(f"Starting bulk load of {len(matches)} matches.")
        
        for i, match in enumerate(matches):
            try:
                # Mỗi trận đấu được xử lý trong một transaction con (sử dụng savepoint)
                # Nếu một trận lỗi, chỉ savepoint đó được rollback, transaction chính vẫn có thể commit.
                with self.session.begin_nested():
                    self._load_single_match(match)
                results["success"] += 1
                logger.debug(f"Successfully processed match {i+1}/{results['total']} (ExtID: {match.external_id})")
            except Exception as e:
                # Lỗi đã được log bên trong, chỉ cần cập nhật kết quả
                results["failed"] += 1
                results["failed_ids"].append(getattr(match, 'external_id', f'index_{i}'))
                logger.warning(f"Failed to process match {i+1}/{results['total']} (ExtID: {getattr(match, 'external_id', 'N/A')}).")
        
        self.clear_cache()
        logger.info("Bulk load completed.", extra={"results": results})
        return results

    def clear_cache(self):
        """Xóa cache sau khi hoàn tất một lần bulk load."""
        self._entity_cache.clear()
        logger.debug("Loader entity cache cleared.")