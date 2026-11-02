# elt_pipeline/load/match_loader.py
"""
PostgreSQL Match Loader - Full Bundle Implementation.

Loads ALL data from a ParsedMatchBundle into the database:
  - Leagues, Seasons, Teams, Stadiums, Referees, Players
  - Matches
  - MatchEvents
  - Lineups
  - SquadAvailability (with match_id linkage)
  - MatchPlayerStats
  - MatchTeamStats

Design:
  - Implements AbstractLoader (DIP)
  - Each entity upserted idempotently (safe to rerun)
  - In-memory cache per loader instance to avoid redundant DB lookups
  - All SQL is raw text (no ORM bloat) - fast and transparent
  - Per-bundle nested transactions: one bundle failure = rollback that bundle only
"""

import logging
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, Generator

from sqlalchemy import text
from sqlalchemy.orm import Session

from elt_pipeline.load.base_loader import AbstractLoader, LoaderError
from elt_pipeline.transform.data_structures import (
    ParsedMatchBundle,
    ParsedMatch,
    ParsedTeam,
    ParsedStadium,
    ParsedReferee,
    ParsedLeague,
    ParsedSeason,
    ParsedPlayer,
    ParsedMatchEvent,
    ParsedLineup,
    ParsedSquadAvailability,
    ParsedMatchPlayerStats,
    ParsedMatchTeamStats,
)
from utils.external_mapping import get_internal_id, upsert_mapping

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# MatchLoader
# ─────────────────────────────────────────────────────────────────────────────

class MatchLoader(AbstractLoader):
    """
    Full PostgreSQL loader for ParsedMatchBundle objects.

    Usage:
        with DatabaseConnector.session_scope() as session:
            loader = MatchLoader(session)
            loader.bulk_load(bundles)
    """

    SOURCE_SYSTEM = "sofascore"

    def __init__(self, session: Session):
        self._session = session
        # In-memory cache: "entity_type:external_id" -> internal_id
        # Avoids N+1 DB lookups for the same team/player across many matches.
        self._cache: Dict[str, int] = {}

    # ── Public interface (AbstractLoader) ─────────────────────────────────────

    def load_bundle(self, bundle: ParsedMatchBundle) -> int:
        """Load one bundle atomically. Returns internal match ID."""
        with self._nested_transaction():
            return self._load_full_bundle(bundle)

    def bulk_load(self, bundles: List[ParsedMatchBundle]) -> Dict[str, Any]:
        """Load multiple bundles, capturing per-bundle errors without aborting the batch."""
        results: Dict[str, Any] = {
            "total": len(bundles),
            "success": 0,
            "failed": 0,
            "failed_ids": [],
        }
        if not bundles:
            return results

        logger.info("Starting bulk load of %d bundles.", len(bundles))

        for i, bundle in enumerate(bundles):
            ext_id = bundle.match.external_id
            try:
                match_id = self.load_bundle(bundle)
                results["success"] += 1
                logger.debug(
                    "[%d/%d] Loaded match ext_id=%d → internal_id=%d",
                    i + 1, len(bundles), ext_id, match_id,
                )
            except Exception as exc:
                results["failed"] += 1
                results["failed_ids"].append(ext_id)
                logger.warning(
                    "[%d/%d] Failed to load match ext_id=%d: %s",
                    i + 1, len(bundles), ext_id, exc,
                    exc_info=True,
                )

        self._cache.clear()
        logger.info(
            "Bulk load complete: %d success, %d failed (of %d total).",
            results["success"], results["failed"], results["total"],
        )
        return results

    # ── Internal orchestration ────────────────────────────────────────────────

    def _load_full_bundle(self, bundle: ParsedMatchBundle) -> int:
        """
        Persist all entities in dependency order.
        Returns the internal match_id.
        """
        match = bundle.match

        # 1. Resolve FK dependencies first (entities that Matches references)
        league_id  = self._upsert_league(match.season.league)
        season_id  = self._upsert_season(match.season, league_id)
        home_id    = self._upsert_team(match.home_team)
        away_id    = self._upsert_team(match.away_team)
        stadium_id = self._upsert_stadium(match.stadium) if match.stadium else self._resolve_team_stadium(match.home_team)
        referee_id = self._upsert_referee(match.referee) if match.referee else None

        if not all([season_id, home_id, away_id]):
            raise LoaderError(
                f"Cannot load match {match.external_id}: missing season/home_team/away_team IDs."
            )

        # 2. Upsert Match (core row)
        match_id = self._upsert_match(match, season_id, home_id, away_id, stadium_id, referee_id)

        # 3. Load child entities (best-effort: errors logged, not raised)
        self._load_events(bundle.events, match_id, home_id, away_id)
        self._load_lineups(bundle.lineups, match_id)
        self._load_squad_availability(bundle.squad_availability, match_id)
        self._load_player_stats(bundle.player_stats, match_id)
        self._load_team_stats(bundle.team_stats, match_id, home_id, away_id)

        return match_id

    # ── Entity upsert helpers ─────────────────────────────────────────────────

    def _upsert_league(self, league: ParsedLeague) -> int:
        cache_key = f"league:{league.external_id}"
        if cached := self._cache.get(cache_key):
            return cached

        if internal_id := get_internal_id(str(league.external_id), "league", self.SOURCE_SYSTEM, self._session):
            self._cache[cache_key] = internal_id
            return internal_id

        internal_id = self._session.execute(text("""
            INSERT INTO "Leagues" (name, country, external_id)
            VALUES (:name, :country, :ext_id)
            ON CONFLICT (name) DO UPDATE SET
                country     = EXCLUDED.country,
                external_id = COALESCE("Leagues".external_id, EXCLUDED.external_id),
                updated_at  = NOW()
            RETURNING id
        """), {
            "name":    league.name.strip(),
            "country": (league.country or "Unknown").strip(),
            "ext_id":  league.external_id,
        }).scalar_one()

        upsert_mapping(str(league.external_id), internal_id, "league", self.SOURCE_SYSTEM, session=self._session)
        self._cache[cache_key] = internal_id
        return internal_id

    def _upsert_season(self, season: ParsedSeason, league_id: int) -> int:
        cache_key = f"season:{season.external_id}"
        if cached := self._cache.get(cache_key):
            return cached

        if internal_id := get_internal_id(str(season.external_id), "season", self.SOURCE_SYSTEM, self._session):
            self._cache[cache_key] = internal_id
            return internal_id

        internal_id = self._session.execute(text("""
            INSERT INTO "Seasons" (league_id, name, start_year, end_year)
            VALUES (:lid, :name, :sy, :ey)
            ON CONFLICT (league_id, name) DO UPDATE SET
                start_year = EXCLUDED.start_year,
                end_year   = EXCLUDED.end_year
            RETURNING id
        """), {
            "lid":  league_id,
            "name": season.name,
            "sy":   season.start_year,
            "ey":   season.end_year,
        }).scalar_one()

        upsert_mapping(str(season.external_id), internal_id, "season", self.SOURCE_SYSTEM, session=self._session)
        self._cache[cache_key] = internal_id
        return internal_id

    def _upsert_stadium(self, stadium: ParsedStadium) -> Optional[int]:
        if not stadium or not stadium.external_id:
            return None
        cache_key = f"stadium:{stadium.external_id}"
        if cached := self._cache.get(cache_key):
            return cached

        if internal_id := get_internal_id(str(stadium.external_id), "stadium", self.SOURCE_SYSTEM, self._session):
            self._cache[cache_key] = internal_id
            return internal_id

        internal_id = self._session.execute(text("""
            INSERT INTO "Stadiums" (name, city, capacity, latitude, longitude)
            VALUES (:name, :city, :cap, :lat, :lng)
            ON CONFLICT (name) DO UPDATE SET
                city       = COALESCE(EXCLUDED.city, "Stadiums".city),
                capacity   = COALESCE(EXCLUDED.capacity, "Stadiums".capacity),
                updated_at = NOW()
            RETURNING id
        """), {
            "name": stadium.name,
            "city": stadium.city,
            "cap":  stadium.capacity,
            "lat":  stadium.latitude,
            "lng":  stadium.longitude,
        }).scalar_one()

        upsert_mapping(str(stadium.external_id), internal_id, "stadium", self.SOURCE_SYSTEM, session=self._session)
        self._cache[cache_key] = internal_id
        return internal_id

    def _upsert_team(self, team: ParsedTeam) -> int:
        cache_key = f"team:{team.external_id}"
        if cached := self._cache.get(cache_key):
            return cached

        if internal_id := get_internal_id(str(team.external_id), "team", self.SOURCE_SYSTEM, self._session):
            self._cache[cache_key] = internal_id
            return internal_id

        # Upsert stadium nested inside team (if present)
        stadium_id = self._upsert_stadium(team.stadium) if team.stadium else None

        internal_id = self._session.execute(text("""
            INSERT INTO "Teams" (name, short_name, stadium_id, logo_url, established_year)
            VALUES (:name, :short, :stadium_id, :logo, :year)
            ON CONFLICT (name) DO UPDATE SET
                short_name  = COALESCE(EXCLUDED.short_name, "Teams".short_name),
                logo_url    = COALESCE(EXCLUDED.logo_url, "Teams".logo_url),
                updated_at  = NOW()
            RETURNING id
        """), {
            "name":      team.name,
            "short":     team.short_name,
            "stadium_id": stadium_id,
            "logo":      team.logo_url,
            "year":      team.established_year,
        }).scalar_one()

        upsert_mapping(str(team.external_id), internal_id, "team", self.SOURCE_SYSTEM, session=self._session)
        self._cache[cache_key] = internal_id
        return internal_id

    def _upsert_referee(self, referee: ParsedReferee) -> Optional[int]:
        if not referee or not referee.external_id:
            return None
        cache_key = f"referee:{referee.external_id}"
        if cached := self._cache.get(cache_key):
            return cached

        if internal_id := get_internal_id(str(referee.external_id), "referee", self.SOURCE_SYSTEM, self._session):
            self._cache[cache_key] = internal_id
            return internal_id

        internal_id = self._session.execute(text("""
            INSERT INTO "Referees" (name, country, date_of_birth)
            VALUES (:name, :country, :dob)
            ON CONFLICT (name, country) DO UPDATE SET
                date_of_birth = COALESCE(EXCLUDED.date_of_birth, "Referees".date_of_birth)
            RETURNING id
        """), {
            "name":    referee.name,
            "country": referee.country,
            "dob":     referee.date_of_birth,
        }).scalar_one()

        upsert_mapping(str(referee.external_id), internal_id, "referee", self.SOURCE_SYSTEM, session=self._session)
        self._cache[cache_key] = internal_id
        return internal_id

    def _upsert_player(self, player: ParsedPlayer) -> Optional[int]:
        if not player or not player.external_id:
            return None
        cache_key = f"player:{player.external_id}"
        if cached := self._cache.get(cache_key):
            return cached

        if internal_id := get_internal_id(str(player.external_id), "player", self.SOURCE_SYSTEM, self._session):
            self._cache[cache_key] = internal_id
            return internal_id

        position_val = player.position.value if player.position else None
        internal_id = self._session.execute(text("""
            INSERT INTO "Players" (name, position, date_of_birth, nationality, height)
            VALUES (:name, :pos, :dob, :nat, :height)
            ON CONFLICT (name, date_of_birth) DO UPDATE SET
                position    = COALESCE(EXCLUDED.position, "Players".position),
                nationality = COALESCE(EXCLUDED.nationality, "Players".nationality),
                height      = COALESCE(EXCLUDED.height, "Players".height),
                updated_at  = NOW()
            RETURNING id
        """), {
            "name":   player.name,
            "pos":    position_val,
            "dob":    player.date_of_birth,
            "nat":    player.nationality,
            "height": player.height,
        }).scalar_one()

        upsert_mapping(str(player.external_id), internal_id, "player", self.SOURCE_SYSTEM, session=self._session)
        self._cache[cache_key] = internal_id
        return internal_id

    def _upsert_match(
        self,
        match: ParsedMatch,
        season_id: int,
        home_id: int,
        away_id: int,
        stadium_id: Optional[int],
        referee_id: Optional[int],
    ) -> int:
        cache_key = f"match:{match.external_id}"
        if cached := self._cache.get(cache_key):
            return cached

        if internal_id := get_internal_id(str(match.external_id), "match", self.SOURCE_SYSTEM, self._session):
            # Still update mutable fields (status, score) in case this is a re-run
            self._session.execute(text("""
                UPDATE "Matches" SET
                    status                = :status,
                    outcome               = :outcome,
                    home_goals            = :hg,
                    away_goals            = :ag,
                    half_time_home_goals  = :hthg,
                    half_time_away_goals  = :htag,
                    attendance            = COALESCE(:att, attendance),
                    updated_at            = NOW()
                WHERE id = :id
            """), {
                "status":  match.status.value,
                "outcome": match.outcome.value if match.outcome else None,
                "hg": match.home_goals, "ag": match.away_goals,
                "hthg": match.half_time_home_goals, "htag": match.half_time_away_goals,
                "att": match.attendance,
                "id": internal_id,
            })
            self._cache[cache_key] = internal_id
            return internal_id

        internal_id = self._session.execute(text("""
            INSERT INTO "Matches" (
                season_id, home_team_id, away_team_id,
                match_datetime, match_week,
                stadium_id, referee_id,
                status, outcome,
                home_goals, away_goals,
                half_time_home_goals, half_time_away_goals,
                attendance
            ) VALUES (
                :sid, :hid, :aid,
                :dt, :mw,
                :st_id, :ref_id,
                :status, :outcome,
                :hg, :ag,
                :hthg, :htag,
                :att
            )
            ON CONFLICT (season_id, home_team_id, away_team_id, match_datetime)
            DO UPDATE SET
                status               = EXCLUDED.status,
                outcome              = EXCLUDED.outcome,
                home_goals           = EXCLUDED.home_goals,
                away_goals           = EXCLUDED.away_goals,
                half_time_home_goals = EXCLUDED.half_time_home_goals,
                half_time_away_goals = EXCLUDED.half_time_away_goals,
                attendance           = COALESCE(EXCLUDED.attendance, "Matches".attendance),
                updated_at           = NOW()
            RETURNING id
        """), {
            "sid": season_id, "hid": home_id, "aid": away_id,
            "dt":  match.match_datetime, "mw": match.match_week,
            "st_id": stadium_id, "ref_id": referee_id,
            "status":  match.status.value,
            "outcome": match.outcome.value if match.outcome else None,
            "hg": match.home_goals,    "ag": match.away_goals,
            "hthg": match.half_time_home_goals, "htag": match.half_time_away_goals,
            "att": match.attendance,
        }).scalar_one()

        upsert_mapping(str(match.external_id), internal_id, "match", self.SOURCE_SYSTEM, session=self._session)
        self._cache[cache_key] = internal_id
        return internal_id

    # ── Child entity loaders (best-effort, errors logged) ─────────────────────

    def _load_events(
        self,
        events: List[ParsedMatchEvent],
        match_id: int,
        home_team_internal_id: int,
        away_team_internal_id: int,
    ) -> None:
        if not events:
            return
        # Delete existing events for this match (idempotent replacement strategy)
        self._session.execute(
            text('DELETE FROM "MatchEvents" WHERE match_id = :mid'),
            {"mid": match_id},
        )
        rows_inserted = 0
        for event in events:
            try:
                player_id = self._upsert_player(event.player) if event.player else None
                related_player_id = self._upsert_player(event.related_player) if event.related_player else None

                # Map team → internal ID
                team_internal_id: Optional[int] = None
                if event.team:
                    team_internal_id = get_internal_id(
                        str(event.team.external_id), "team", self.SOURCE_SYSTEM, self._session
                    )

                self._session.execute(text("""
                    INSERT INTO "MatchEvents" (
                        match_id, minute, event_type, period,
                        team_id, player_id, related_player_id, description
                    ) VALUES (
                        :mid, :min, :etype, :period,
                        :tid, :pid, :rpid, :desc
                    )
                """), {
                    "mid":    match_id,
                    "min":    event.minute,
                    "etype":  event.event_type.value,
                    "period": event.period.value,
                    "tid":    team_internal_id,
                    "pid":    player_id,
                    "rpid":   related_player_id,
                    "desc":   event.description,
                })
                rows_inserted += 1
            except Exception as exc:
                logger.warning("Failed to insert event for match %d: %s", match_id, exc)

        logger.debug("Inserted %d events for match %d.", rows_inserted, match_id)

    def _load_lineups(self, lineups: List[ParsedLineup], match_id: int) -> None:
        if not lineups:
            return
        # Idempotent: delete then reinsert
        self._session.execute(
            text('DELETE FROM "Lineups" WHERE match_id = :mid'),
            {"mid": match_id},
        )
        rows_inserted = 0
        for lu in lineups:
            try:
                player_id = self._upsert_player(lu.player)
                team_id   = self._upsert_team(lu.team)
                if not player_id or not team_id:
                    continue

                self._session.execute(text("""
                    INSERT INTO "Lineups" (
                        match_id, player_id, team_id,
                        is_starter, shirt_number, is_captain, position_in_lineup
                    ) VALUES (
                        :mid, :pid, :tid,
                        :starter, :shirt, :captain, :pos
                    )
                    ON CONFLICT (match_id, player_id) DO UPDATE SET
                        is_starter       = EXCLUDED.is_starter,
                        shirt_number     = EXCLUDED.shirt_number,
                        is_captain       = EXCLUDED.is_captain,
                        position_in_lineup = EXCLUDED.position_in_lineup
                """), {
                    "mid":     match_id,
                    "pid":     player_id,
                    "tid":     team_id,
                    "starter": lu.is_starter,
                    "shirt":   lu.shirt_number,
                    "captain": lu.is_captain,
                    "pos":     lu.position_in_lineup,
                })
                rows_inserted += 1
            except Exception as exc:
                logger.warning("Failed to insert lineup for match %d: %s", match_id, exc)

        logger.debug("Inserted %d lineups for match %d.", rows_inserted, match_id)

    def _load_squad_availability(
        self, records: List[ParsedSquadAvailability], match_id: int
    ) -> None:
        if not records:
            return
        rows_inserted = 0
        for rec in records:
            try:
                player_id = self._upsert_player(rec.player)
                team_id   = self._upsert_team(rec.team)
                if not player_id or not team_id:
                    continue

                self._session.execute(text("""
                    INSERT INTO "SquadAvailability" (
                        match_id, player_id, team_id, status, notes
                    ) VALUES (
                        :mid, :pid, :tid, :status, :notes
                    )
                    ON CONFLICT (match_id, player_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        notes  = EXCLUDED.notes
                """), {
                    "mid":    match_id,
                    "pid":    player_id,
                    "tid":    team_id,
                    "status": rec.status.value,
                    "notes":  rec.notes,
                })
                rows_inserted += 1
            except Exception as exc:
                logger.warning("Failed to insert squad availability for match %d: %s", match_id, exc)

        logger.debug("Inserted %d squad availability records for match %d.", rows_inserted, match_id)

    def _load_player_stats(
        self, stats_list: List[ParsedMatchPlayerStats], match_id: int
    ) -> None:
        if not stats_list:
            return
        rows_inserted = 0
        for stats in stats_list:
            try:
                player_id = self._upsert_player(stats.player)
                team_id   = self._upsert_team(stats.team)
                if not player_id or not team_id:
                    continue

                self._session.execute(text("""
                    INSERT INTO "MatchPlayerStats" (
                        match_id, player_id, team_id,
                        is_starter, minutes_played,
                        goals, assists, shots, shots_on_target,
                        passes, accurate_passes, key_passes,
                        tackles, interceptions,
                        fouls_committed, fouls_drawn,
                        yellow_cards, red_cards, saves,
                        substituted_in_minute, substituted_out_minute
                    ) VALUES (
                        :mid, :pid, :tid,
                        :starter, :mins,
                        :goals, :assists, :shots, :sot,
                        :passes, :acc_passes, :kp,
                        :tackles, :intercepts,
                        :fc, :fd,
                        :yc, :rc, :saves,
                        :sub_in, :sub_out
                    )
                    ON CONFLICT (match_id, player_id) DO UPDATE SET
                        minutes_played   = EXCLUDED.minutes_played,
                        goals            = EXCLUDED.goals,
                        assists          = EXCLUDED.assists,
                        shots            = EXCLUDED.shots,
                        shots_on_target  = EXCLUDED.shots_on_target,
                        passes           = EXCLUDED.passes,
                        accurate_passes  = EXCLUDED.accurate_passes,
                        key_passes       = EXCLUDED.key_passes,
                        tackles          = EXCLUDED.tackles,
                        interceptions    = EXCLUDED.interceptions,
                        fouls_committed  = EXCLUDED.fouls_committed,
                        fouls_drawn      = EXCLUDED.fouls_drawn,
                        yellow_cards     = EXCLUDED.yellow_cards,
                        red_cards        = EXCLUDED.red_cards,
                        saves            = EXCLUDED.saves,
                        updated_at       = NOW()
                """), {
                    "mid": match_id, "pid": player_id, "tid": team_id,
                    "starter": stats.is_starter, "mins": stats.minutes_played,
                    "goals": stats.goals, "assists": stats.assists,
                    "shots": stats.shots, "sot": stats.shots_on_target,
                    "passes": stats.passes, "acc_passes": stats.accurate_passes,
                    "kp": stats.key_passes, "tackles": stats.tackles,
                    "intercepts": stats.interceptions,
                    "fc": stats.fouls_committed, "fd": stats.fouls_drawn,
                    "yc": stats.yellow_cards, "rc": stats.red_cards,
                    "saves": stats.saves,
                    "sub_in":  stats.substituted_in_minute,
                    "sub_out": stats.substituted_out_minute,
                })
                rows_inserted += 1
            except Exception as exc:
                logger.warning("Failed to insert player stats for match %d: %s", match_id, exc)

        logger.debug("Inserted %d player stats rows for match %d.", rows_inserted, match_id)

    def _load_team_stats(
        self,
        stats_list: List[ParsedMatchTeamStats],
        match_id: int,
        home_internal_id: int,
        away_internal_id: int,
    ) -> None:
        if not stats_list:
            return
        rows_inserted = 0
        for stats in stats_list:
            try:
                team_id = get_internal_id(
                    str(stats.team.external_id), "team", self.SOURCE_SYSTEM, self._session
                )
                if not team_id:
                    team_id = self._upsert_team(stats.team)

                location = "Home" if team_id == home_internal_id else "Away"

                self._session.execute(text("""
                    INSERT INTO "MatchTeamStats" (
                        match_id, team_id, location,
                        possession_percentage,
                        total_shots, shots_on_target, shots_off_target, blocked_shots,
                        fouls_committed, corners, offsides,
                        yellow_cards, red_cards, saves
                    ) VALUES (
                        :mid, :tid, :loc,
                        :poss,
                        :ts, :sot, :soft, :bshot,
                        :fc, :corners, :off,
                        :yc, :rc, :saves
                    )
                    ON CONFLICT (match_id, team_id) DO UPDATE SET
                        possession_percentage = EXCLUDED.possession_percentage,
                        total_shots           = EXCLUDED.total_shots,
                        shots_on_target       = EXCLUDED.shots_on_target,
                        shots_off_target      = EXCLUDED.shots_off_target,
                        blocked_shots         = EXCLUDED.blocked_shots,
                        fouls_committed       = EXCLUDED.fouls_committed,
                        corners               = EXCLUDED.corners,
                        offsides              = EXCLUDED.offsides,
                        yellow_cards          = EXCLUDED.yellow_cards,
                        red_cards             = EXCLUDED.red_cards,
                        saves                 = EXCLUDED.saves,
                        updated_at            = NOW()
                """), {
                    "mid": match_id, "tid": team_id, "loc": location,
                    "poss": float(stats.possession_percentage) if stats.possession_percentage else None,
                    "ts": stats.total_shots, "sot": stats.shots_on_target,
                    "soft": stats.shots_off_target, "bshot": stats.blocked_shots,
                    "fc": stats.fouls_committed, "corners": stats.corners,
                    "off": stats.offsides, "yc": stats.yellow_cards,
                    "rc": stats.red_cards, "saves": stats.saves,
                })
                rows_inserted += 1
            except Exception as exc:
                logger.warning("Failed to insert team stats for match %d: %s", match_id, exc)

        logger.debug("Inserted %d team stats rows for match %d.", rows_inserted, match_id)

    # ── Utility helpers ───────────────────────────────────────────────────────

    def _resolve_team_stadium(self, team: ParsedTeam) -> Optional[int]:
        """Fallback: look up the team's home stadium from DB."""
        if not team.external_id:
            return None
        result = self._session.execute(text("""
            SELECT t.stadium_id
            FROM "Teams" t
            JOIN "ExternalMapping" em ON em.internal_id = t.id
            WHERE em.external_id = :ext AND em.entity_type = 'team' AND em.source_system = :src
            LIMIT 1
        """), {"ext": str(team.external_id), "src": self.SOURCE_SYSTEM}).scalar()
        return result

    @contextmanager
    def _nested_transaction(self) -> Generator:
        """
        Wraps a block in a SAVEPOINT (nested transaction).
        On failure, rolls back to the savepoint - other bundles in the session
        remain unaffected.
        """
        if self._session.in_transaction():
            with self._session.begin_nested():
                yield
        else:
            with self._session.begin():
                yield


# ── Convenience alias for backward compatibility ──────────────────────────────
# Old code referenced SofaScoreLoader - redirect cleanly.
SofaScoreLoader = MatchLoader

