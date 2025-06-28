"""
SofaScore client: crawl match list per season and insert directly into database.
Includes:
- Fetching match list via SofaScore API
- Fetching match detail (lineups, stats, incidents)
- Parsing into DB schema format
- Inserting League, Season, Teams, Stadium, Match, Referee
- Upserting external_id mapping
"""

import time
import logging
import requests
from typing import List, Dict, Any, Optional, Tuple

from config.settings import get_config
from .sofascore_endpoints import SofaScoreEndpoints, build_url
from utils.db_connector import DatabaseConnector
from utils.external_mapping import upsert_mapping
from utils.logging_config import setup_logging
from config.core_constants import SofascoreConstants
from config.field_mappings import convert_datetime

setup_logging()
logger = logging.getLogger(__name__)

config = get_config()
HEADERS = config.sofascore.get_random_headers()
TIMEOUT = config.sofascore.get_timeout()
DELAY = config.sofascore.get_delay_seconds()
RETRY = config.sofascore.get_retry_count()
TOURNAMENT_ID = config.sofascore.tournament_id


class SofaScoreClient:
    """SofaScore API client for fetching and storing football match data."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def fetch_match_list(self, season_id: int, season_name: str) -> List[Dict[str, Any]]:
        """Fetch all matches for a given season with pagination."""
        matches = []
        page = 0
        retry_count = 0
        
        while True:
            page += 1
            url = build_url(
                SofaScoreEndpoints.SEASON_MATCHES,
                tournament_id=TOURNAMENT_ID,
                season_id=season_id,
                page=page
            )
            
            try:
                logger.info(f"Fetching page {page} for season {season_name}")
                resp = self.session.get(url, timeout=TIMEOUT)
                
                if resp.status_code == 404:
                    logger.info(f"No more data for season {season_name}, page {page}")
                    break
                    
                resp.raise_for_status()
                data = resp.json()
                events = data.get("events", [])
                
                if not events:
                    logger.info(f"No events found on page {page} for season {season_name}")
                    break
                    
                matches.extend(events)
                retry_count = 0  # Reset retry count on successful request
                time.sleep(DELAY)
                
            except requests.exceptions.RequestException as e:
                retry_count += 1
                logger.warning(f"Error fetching page {page} (attempt {retry_count}/{RETRY}): {e}")
                
                if retry_count >= RETRY:
                    logger.error(f"Max retries exceeded for page {page}, moving to next page")
                    break
                    
                time.sleep(DELAY * retry_count)  # Exponential backoff
                continue
                
        logger.info(f"Fetched {len(matches)} matches for season {season_name}")
        return matches

    def fetch_match_detail(self, match_id: int) -> Optional[Dict[str, Any]]:
        """Fetch detailed information for a specific match."""
        url = build_url(SofaScoreEndpoints.MATCH_DETAIL, match_id=match_id)
        
        for attempt in range(RETRY + 1):
            try:
                logger.debug(f"Fetching detail for match {match_id} (attempt {attempt + 1})")
                resp = self.session.get(url, timeout=TIMEOUT)
                resp.raise_for_status()
                return resp.json()
                
            except requests.exceptions.RequestException as e:
                if attempt == RETRY:
                    logger.error(f"Failed to fetch detail for match {match_id} after {RETRY + 1} attempts: {e}")
                    return None
                    
                logger.warning(f"Attempt {attempt + 1} failed for match {match_id}: {e}")
                time.sleep(DELAY * (attempt + 1))
                
        return None

    def fetch_lineups(self, match_id: int) -> Optional[Dict[str, Any]]:
        """Fetch lineups for a specific match."""
        url = build_url(SofaScoreEndpoints.MATCH_LINEUPS, match_id=match_id)
        
        for attempt in range(RETRY + 1):
            try:
                logger.debug(f"Fetching lineups for match {match_id} (attempt {attempt + 1})")
                resp = self.session.get(url, timeout=TIMEOUT)
                resp.raise_for_status()
                return resp.json()
                
            except requests.exceptions.RequestException as e:
                if attempt == RETRY:
                    logger.error(f"Failed to fetch lineups for match {match_id} after {RETRY + 1} attempts: {e}")
                    return None
                    
                logger.warning(f"Attempt {attempt + 1} failed for match {match_id}: {e}")
                time.sleep(DELAY * (attempt + 1))
                
        return None

    def fetch_statistics(self, match_id: int) -> Optional[Dict[str, Any]]:
        """Fetch statistics for a specific match."""
        url = build_url(SofaScoreEndpoints.MATCH_STATISTICS, match_id=match_id)
        
        for attempt in range(RETRY + 1):
            try:
                logger.debug(f"Fetching statistics for match {match_id} (attempt {attempt + 1})")
                resp = self.session.get(url, timeout=TIMEOUT)
                resp.raise_for_status()
                return resp.json()
                
            except requests.exceptions.RequestException as e:
                if attempt == RETRY:
                    logger.error(f"Failed to fetch statistics for match {match_id} after {RETRY + 1} attempts: {e}")
                    return None
                    
                logger.warning(f"Attempt {attempt + 1} failed for match {match_id}: {e}")
                time.sleep(DELAY * (attempt + 1))
                
        return None

    def fetch_incidents(self, match_id: int) -> Optional[Dict[str, Any]]:
        """Fetch incidents for a specific match."""
        url = build_url(SofaScoreEndpoints.MATCH_INCIDENTS, match_id=match_id)
        
        for attempt in range(RETRY + 1):
            try:
                logger.debug(f"Fetching incidents for match {match_id} (attempt {attempt + 1})")
                resp = self.session.get(url, timeout=TIMEOUT)
                resp.raise_for_status()
                return resp.json()
                
            except requests.exceptions.RequestException as e:
                if attempt == RETRY:
                    logger.error(f"Failed to fetch incidents for match {match_id} after {RETRY + 1} attempts: {e}")
                    return None
                    
                logger.warning(f"Attempt {attempt + 1} failed for match {match_id}: {e}")
                time.sleep(DELAY * (attempt + 1))
                
        return None

    def _insert_teams(self, session, home_team: Dict[str, Any], away_team: Dict[str, Any]):
        """Insert teams into database and create external mappings."""
        for team in (home_team, away_team):
            team_name = team.get("name")
            team_id = team.get("id")
            
            if not team_name or not team_id:
                logger.warning(f"Missing team data: {team}")
                continue
                
            try:
                session.execute("""
                    INSERT INTO "Teams" (name)
                    VALUES (:name)
                    ON CONFLICT (name) DO NOTHING
                """, {"name": team_name})
                
                # Get the team's internal ID for mapping
                result = session.execute("""
                    SELECT id FROM "Teams" WHERE name = :name
                """, {"name": team_name}).fetchone()
                
                if result:
                    internal_team_id = result[0]
                    upsert_mapping("team", team_id, internal_team_id, "sofascore")
                
            except Exception as e:
                logger.error(f"Failed to insert team {team_name}: {e}")

    def _insert_stadium(self, session, venue: Dict[str, Any]) -> Optional[int]:
        """Insert stadium into database and return stadium ID."""
        if not venue:
            return None
            
        stadium_data = venue.get("stadium", {})
        city_data = venue.get("city", {})
        
        stadium_name = stadium_data.get("name")
        city_name = city_data.get("name")
        
        if not stadium_name:
            return None
            
        try:
            session.execute("""
                INSERT INTO "Stadiums" (name, city)
                VALUES (:name, :city)
                ON CONFLICT (name) DO NOTHING
            """, {
                "name": stadium_name,
                "city": city_name
            })
            
            # Get stadium ID
            result = session.execute("""
                SELECT id FROM "Stadiums" WHERE name = :name
            """, {"name": stadium_name}).fetchone()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Failed to insert stadium {stadium_name}: {e}")
            return None

    def _insert_referee(self, session, referee: Dict[str, Any]) -> Optional[int]:
        """Insert referee into database and create external mapping. Return referee ID."""
        if not referee:
            return None
            
        referee_name = referee.get("name")
        referee_id = referee.get("id")
        
        if not referee_name:
            return None
            
        try:
            session.execute("""
                INSERT INTO "Referees" (name)
                VALUES (:name)
                ON CONFLICT (name) DO NOTHING
            """, {"name": referee_name})
            
            # Get referee's internal ID
            result = session.execute("""
                SELECT id FROM "Referees" WHERE name = :name
            """, {"name": referee_name}).fetchone()
            
            internal_referee_id = result[0] if result else None
            
            if referee_id and internal_referee_id:
                upsert_mapping("referee", referee_id, internal_referee_id, "sofascore")
                
            return internal_referee_id
                
        except Exception as e:
            logger.error(f"Failed to insert referee {referee_name}: {e}")
            return None

    def _insert_match(self, session, match_data: Dict[str, Any], match_datetime, 
                     stadium_id: Optional[int] = None, referee_id: Optional[int] = None) -> Optional[int]:
        """Insert match into database and create external mapping. Return match ID."""
        home_team = match_data.get("homeTeam", {})
        away_team = match_data.get("awayTeam", {})
        status = match_data.get("status", {})
        home_score = match_data.get("homeScore", {})
        away_score = match_data.get("awayScore", {})
        
        match_id = match_data.get("id")
        if not match_id:
            logger.warning("Missing match ID")
            return None
            
        try:
            session.execute("""
                INSERT INTO "Matches" (
                    match_datetime, home_team_id, away_team_id,
                    home_goals, away_goals,
                    half_time_home_goals, half_time_away_goals,
                    status, stadium_id, referee_id
                )
                SELECT :datetime,
                    ht.id, at.id,
                    :hg, :ag, :hthg, :htag, :status, :stadium_id, :referee_id
                FROM "Teams" ht, "Teams" at
                WHERE ht.name = :home_name AND at.name = :away_name
                ON CONFLICT DO NOTHING
            """, {
                "datetime": match_datetime,
                "home_name": home_team.get("name"),
                "away_name": away_team.get("name"),
                "hg": home_score.get("current"),
                "ag": away_score.get("current"),
                "hthg": home_score.get("period1"),
                "htag": away_score.get("period1"),
                "status": status.get("description", "SCHEDULED"),
                "stadium_id": stadium_id,
                "referee_id": referee_id
            })
            
            # Get match's internal ID
            result = session.execute("""
                SELECT m.id FROM "Matches" m
                JOIN "Teams" ht ON m.home_team_id = ht.id
                JOIN "Teams" at ON m.away_team_id = at.id
                WHERE m.match_datetime = :datetime
                  AND ht.name = :home_name 
                  AND at.name = :away_name
            """, {
                "datetime": match_datetime,
                "home_name": home_team.get("name"),
                "away_name": away_team.get("name")
            }).fetchone()
            
            internal_match_id = result[0] if result else None
            
            if internal_match_id:
                upsert_mapping("match", match_id, internal_match_id, "sofascore")
                
            return internal_match_id
            
        except Exception as e:
            logger.error(f"Failed to insert match {match_id}: {e}")
            return None

    def _insert_team_statistics(self, session, stats: Dict[str, Any], match_id: int):
        """Insert team statistics into database."""
        if not stats or not match_id:
            return
            
        teams_stats = stats.get("teams", [])
        
        for team_stat in teams_stats:
            team_data = team_stat.get("team", {})
            team_name = team_data.get("name")
            
            if not team_name:
                continue
                
            # Convert statistics list to dictionary
            stats_list = team_stat.get("statistics", [])
            stats_dict = {stat.get("name"): stat.get("value", 0) for stat in stats_list}
            
            try:
                session.execute("""
                    INSERT INTO "MatchTeamStats" (
                        match_id, team_id,
                        possession_percentage, total_shots, shots_on_target,
                        shots_off_target, blocked_shots,
                        fouls_committed, corners, offsides,
                        yellow_cards, red_cards, saves
                    )
                    SELECT :match_id, t.id, :pos, :shots, :sot, :soff, :blocked,
                           :fouls, :corners, :offsides,
                           :yc, :rc, :saves
                    FROM "Teams" t
                    WHERE t.name = :team_name
                    ON CONFLICT (match_id, team_id) DO NOTHING
                """, {
                    "match_id": match_id,
                    "team_name": team_name,
                    "pos": stats_dict.get("Ball possession", 0),
                    "shots": stats_dict.get("Total shots", 0),
                    "sot": stats_dict.get("Shots on target", 0),
                    "soff": stats_dict.get("Shots off target", 0),
                    "blocked": stats_dict.get("Blocked shots", 0),
                    "fouls": stats_dict.get("Fouls", 0),
                    "corners": stats_dict.get("Corner kicks", 0),
                    "offsides": stats_dict.get("Offsides", 0),
                    "yc": stats_dict.get("Yellow cards", 0),
                    "rc": stats_dict.get("Red cards", 0),
                    "saves": stats_dict.get("Goalkeeper saves", 0)
                })
                
            except Exception as e:
                logger.error(f"Failed to insert team stats for {team_name}: {e}")

    def _insert_player_statistics(self, session, stats: Dict[str, Any], match_id: int):
        """Insert player statistics into database."""
        if not stats or not match_id:
            return
            
        players_stats = stats.get("players", [])
        
        for team_players in players_stats:
            team_data = team_players.get("team", {})
            team_name = team_data.get("name")
            
            if not team_name:
                continue
                
            player_stats_list = team_players.get("statistics", [])
            
            for player_stat in player_stats_list:
                player_data = player_stat.get("player")
                
                if not player_data:
                    continue
                    
                player_name = player_data.get("name")
                player_id = player_data.get("id")
                
                if not player_name:
                    continue
                
                # Convert player statistics to dictionary
                stats_list = player_stat.get("stats", [])
                stats_dict = {stat.get("name"): stat.get("value", 0) for stat in stats_list}
                
                try:
                    # First ensure player exists
                    session.execute("""
                        INSERT INTO "Players" (name)
                        VALUES (:name)
                        ON CONFLICT (name) DO NOTHING
                    """, {"name": player_name})
                    
                    # Get player's internal ID for mapping
                    result = session.execute("""
                        SELECT id FROM "Players" WHERE name = :name
                    """, {"name": player_name}).fetchone()
                    
                    if result and player_id:
                        internal_player_id = result[0]
                        upsert_mapping("player", player_id, internal_player_id, "sofascore")
                    
                    # Then insert player stats
                    session.execute("""
                        INSERT INTO "MatchPlayerStats" (
                            match_id, team_id, player_id, is_starter,
                            minutes_played, goals, assists, shots,
                            shots_on_target, passes, accurate_passes,
                            key_passes, tackles, interceptions,
                            fouls_committed, fouls_drawn,
                            yellow_cards, red_cards, saves
                        )
                        SELECT :match_id, t.id, p.id, true,
                               :min, :goals, :assists, :shots,
                               :sot, :passes, :acc_passes, :key,
                               :tackles, :intercept, :fouls_c, :fouls_d,
                               :yc, :rc, :saves
                        FROM "Teams" t, "Players" p
                        WHERE t.name = :team_name AND p.name = :player_name
                        ON CONFLICT (match_id, team_id, player_id) DO NOTHING
                    """, {
                        "match_id": match_id,
                        "team_name": team_name,
                        "player_name": player_name,
                        "min": stats_dict.get("Minutes played", 0),
                        "goals": stats_dict.get("Goals", 0),
                        "assists": stats_dict.get("Assists", 0),
                        "shots": stats_dict.get("Shots", 0),
                        "sot": stats_dict.get("Shots on target", 0),
                        "passes": stats_dict.get("Total passes", 0),
                        "acc_passes": stats_dict.get("Accurate passes", 0),
                        "key": stats_dict.get("Key passes", 0),
                        "tackles": stats_dict.get("Tackles", 0),
                        "intercept": stats_dict.get("Interceptions", 0),
                        "fouls_c": stats_dict.get("Fouls committed", 0),
                        "fouls_d": stats_dict.get("Fouls drawn", 0),
                        "yc": stats_dict.get("Yellow cards", 0),
                        "rc": stats_dict.get("Red cards", 0),
                        "saves": stats_dict.get("Saves", 0)
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to insert player stats for {player_name}: {e}")

    def _insert_lineups(self, session, lineups: Dict[str, Any], match_id: int):
        """Insert lineups into database."""
        if not lineups or not match_id:
            return
            
        home_lineup = lineups.get("home", {})
        away_lineup = lineups.get("away", {})
        
        for team_lineup in [home_lineup, away_lineup]:
            team_data = team_lineup.get("team", {})
            team_name = team_data.get("name")
            
            if not team_name:
                continue
                
            # Insert starting XI
            starting_players = team_lineup.get("players", [])
            for player_data in starting_players:
                self._insert_lineup_player(session, player_data, team_name, match_id, is_starter=True)
            
            # Insert substitutes
            substitutes = team_lineup.get("substitutes", [])
            for player_data in substitutes:
                self._insert_lineup_player(session, player_data, team_name, match_id, is_starter=False)

    def _insert_lineup_player(self, session, player_data: Dict[str, Any], team_name: str, match_id: int, is_starter: bool):
        """Insert individual lineup player into database."""
        player_info = player_data.get("player", {})
        player_name = player_info.get("name")
        player_id = player_info.get("id")
        shirt_number = player_data.get("shirtNumber")
        position = player_data.get("position")
        substitute = player_data.get("substitute", False)
        
        if not player_name:
            return
            
        try:
            # Ensure player exists
            session.execute("""
                INSERT INTO "Players" (name, position)
                VALUES (:name, :position)
                ON CONFLICT (name) DO UPDATE SET position = EXCLUDED.position
            """, {
                "name": player_name,
                "position": position
            })
            
            # Get player's internal ID and create external mapping
            result = session.execute("""
                SELECT id FROM "Players" WHERE name = :name
            """, {"name": player_name}).fetchone()
            
            if result and player_id:
                internal_player_id = result[0]
                upsert_mapping("player", player_id, internal_player_id, "sofascore")
            
            # Insert lineup entry
            session.execute("""
                INSERT INTO "MatchLineups" (
                    match_id, team_id, player_id,
                    is_starter, shirt_number, position, is_substitute
                )
                SELECT :match_id, t.id, p.id,
                    :is_starter, :shirt_number, :position, :is_substitute
                FROM "Teams" t, "Players" p
                WHERE t.name = :team_name
                    AND p.name = :player_name
                ON CONFLICT (match_id, team_id, player_id) DO NOTHING
            """, {
                "match_id": match_id,
                "team_name": team_name,
                "player_name": player_name,
                "is_starter": is_starter,
                "shirt_number": shirt_number,
                "position": position,
                "is_substitute": substitute
            })
            
        except Exception as e:
            logger.error(f"Failed to insert lineup player {player_name}: {e}")

    def _insert_match_incidents(self, session, incidents: Dict[str, Any], match_id: int):
        """Insert match incidents into database."""
        if not incidents or not match_id:
            return
            
        incidents_list = incidents.get("incidents", [])
        
        for event in incidents_list:
            player_data = event.get("player")
            team_data = event.get("team", {})
            time_data = event.get("time", {})
            
            if not player_data:
                continue
                
            player_name = player_data.get("name")
            player_id = player_data.get("id")
            team_name = team_data.get("name")
            
            if not player_name or not team_name:
                continue
                
            try:
                # Ensure player exists
                session.execute("""
                    INSERT INTO "Players" (name)
                    VALUES (:name)
                    ON CONFLICT (name) DO NOTHING
                """, {"name": player_name})
                
                # Get player's internal ID and create external mapping
                result = session.execute("""
                    SELECT id FROM "Players" WHERE name = :name
                """, {"name": player_name}).fetchone()
                
                if result and player_id:
                    internal_player_id = result[0]
                    upsert_mapping("player", player_id, internal_player_id, "sofascore")
                
                # Insert match event
                session.execute("""
                    INSERT INTO "MatchEvents" (
                        match_id, team_id, player_id,
                        event_type, minute, second,
                        is_important, description
                    )
                    SELECT :match_id, t.id, p.id,
                        :etype, :minute, :second, :important, :desc
                    FROM "Teams" t, "Players" p
                    WHERE t.name = :team_name
                        AND p.name = :player_name
                    ON CONFLICT (match_id, team_id, player_id, event_type, minute) DO NOTHING
                """, {
                    "match_id": match_id,
                    "team_name": team_name,
                    "player_name": player_name,
                    "etype": event.get("incidentType"),
                    "minute": time_data.get("minute"),
                    "second": time_data.get("second"),
                    "important": event.get("isGoal", False) or event.get("isPenalty", False),
                    "desc": event.get("text", "")
                })
                
            except Exception as e:
                logger.error(f"Failed to insert incident for {player_name}: {e}")

    def insert_match_data(self, matches: List[Dict[str, Any]], season_name: str):
        """Insert match data and related information into database."""
        total_matches = len(matches)
        logger.info(f"Processing {total_matches} matches for season {season_name}")
        
        with DatabaseConnector.session_scope() as session:
            for idx, match in enumerate(matches, 1):
                try:
                    match_id = match.get("id")
                    if not match_id:
                        logger.warning(f"Skipping match without ID: {match}")
                        continue
                        
                    logger.info(f"Processing match {idx}/{total_matches}: {match_id}")
                    
                    # Fetch detailed match data
                    match_detail = self.fetch_match_detail(match_id)
                    if not match_detail:
                        logger.warning(f"Skipping match {match_id} - no detail data")
                        continue

                    match_data = match_detail.get("event", {})
                    if not match_data:
                        logger.warning(f"Skipping match {match_id} - no event data")
                        continue
                        
                    home_team = match_data.get("homeTeam", {})
                    away_team = match_data.get("awayTeam", {})
                    referee = match_data.get("referee")
                    venue = match_data.get("venue")

                    # Convert timestamp to datetime
                    start_timestamp = match_data.get("startTimestamp")
                    match_datetime = convert_datetime(start_timestamp) if start_timestamp else None
                    
                    if not match_datetime:
                        logger.warning(f"Skipping match {match_id} - no valid datetime")
                        continue

                    # Insert related data and get IDs
                    self._insert_teams(session, home_team, away_team)
                    stadium_id = self._insert_stadium(session, venue)
                    referee_id = self._insert_referee(session, referee)
                    internal_match_id = self._insert_match(session, match_data, match_datetime, stadium_id, referee_id)
                    
                    if not internal_match_id:
                        logger.warning(f"Failed to get internal match ID for {match_id}")
                        continue

                    # Add delay between match detail fetches
                    time.sleep(DELAY)

                    # Fetch and store additional data
                    lineups = self.fetch_lineups(match_id)
                    if lineups:
                        logger.debug(f"Processing lineups for match {match_id}")
                        self._insert_lineups(session, lineups, internal_match_id)
                        
                    time.sleep(DELAY)

                    statistics = self.fetch_statistics(match_id)
                    if statistics:
                        logger.debug(f"Processing statistics for match {match_id}")
                        self._insert_team_statistics(session, statistics, internal_match_id)
                        self._insert_player_statistics(session, statistics, internal_match_id)
                        
                    time.sleep(DELAY)

                    incidents = self.fetch_incidents(match_id)
                    if incidents:
                        logger.debug(f"Processing incidents for match {match_id}")
                        self._insert_match_incidents(session, incidents, internal_match_id)
                        
                    time.sleep(DELAY)

                except Exception as e:
                    logger.error(f"Failed to process match {match.get('id', 'unknown')}: {e}")
                    continue
                    
        logger.info(f"Completed processing matches for season {season_name}")

    def close(self):
        """Close the session."""
        if self.session:
            self.session.close()


def run():
    """Main function to run the SofaScore data extraction."""
    client = SofaScoreClient()
    
    try:
        seasons: List[Tuple[int, str]] = config.sofascore.get_target_seasons_with_ids()
        
        for season_id, season_name in seasons:
            logger.info(f"Starting data extraction for season: {season_name}")
            
            try:
                matches = client.fetch_match_list(season_id, season_name)
                if matches:
                    client.insert_match_data(matches, season_name)
                else:
                    logger.warning(f"No matches found for season {season_name}")
                    
            except Exception as e:
                logger.error(f"Failed to process season {season_name}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Critical error in main execution: {e}")
        
    finally:
        client.close()


if __name__ == "__main__":
    run()