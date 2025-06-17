-- 1. DROP nếu tồn tại (tùy bạn muốn reset)
-- Lưu ý thứ tự drop: bảng con trước bảng cha.
DROP TABLE IF EXISTS "RefereeStats";
DROP TABLE IF EXISTS "BettingOdds";
DROP TABLE IF EXISTS "PlayerSeasonStats";
DROP TABLE IF EXISTS "TeamFormStats";
DROP TABLE IF EXISTS "TeamSeasonLocationStats";
DROP TABLE IF EXISTS "Lineups";
DROP TABLE IF EXISTS "SquadAvailability";
DROP TABLE IF EXISTS "MatchTeamStats";
DROP TABLE IF EXISTS "MatchPlayerStats";
DROP TABLE IF EXISTS "MatchEvents";
DROP TABLE IF EXISTS "Matches";
DROP TABLE IF EXISTS "Players";
DROP TABLE IF EXISTS "Referees";
DROP TABLE IF EXISTS "Teams";
DROP TABLE IF EXISTS "Stadiums";
DROP TABLE IF EXISTS "Seasons";
DROP TABLE IF EXISTS "Leagues";

-- 2. CREATE TYPE ENUMs
CREATE TYPE "MatchOutcome" AS ENUM ('H', 'D', 'A');

CREATE TYPE "MatchStatus" AS ENUM ('SCHEDULED', 'FINISHED', 'POSTPONED', 'CANCELLED' /*, 'IN_PROGRESS' nếu cần realtime*/);

CREATE TYPE "PlayerStatus" AS ENUM ('Available', 'Injured', 'Suspended', 'Doubtful', 'Away on Intl Duty');

CREATE TYPE "LocationType" AS ENUM ('Home', 'Away', 'Overall');

CREATE TYPE "MatchEventType" AS ENUM (
  'goal', 'yellow card', 'red card', 'substitution', 'foul',
  'corner', 'offside', 'penalty', 'own goal', 'missed penalty'
);

CREATE TYPE "MatchPeriod" AS ENUM ('1H', '2H', 'ET1', 'ET2', 'PEN');

-- 3. Bảng Leagues
CREATE TABLE "Leagues" (
  "id" SERIAL PRIMARY KEY,
  "name" VARCHAR(255) UNIQUE NOT NULL,
  "country" VARCHAR(100) NOT NULL,
  "established_year" INT CHECK (established_year > 1800 AND established_year <= EXTRACT(YEAR FROM NOW())::INT),
  "created_at" TIMESTAMP NOT NULL DEFAULT now()
);
COMMENT ON TABLE "Leagues" IS 'Information about football leagues.';
COMMENT ON COLUMN "Leagues"."created_at" IS 'Record creation timestamp';

-- 4. Bảng Seasons
CREATE TABLE "Seasons" (
  "id" SERIAL PRIMARY KEY,
  "league_id" INT NOT NULL,
  "start_year" INT NOT NULL,
  "end_year" INT NOT NULL,
  "name" VARCHAR(255) UNIQUE NOT NULL,
  "champion_team_id" INT NULL,
  "relegated_team_1" INT NULL,
  "relegated_team_2" INT NULL,
  "relegated_team_3" INT NULL,
  "created_at" TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT chk_season_years CHECK (end_year = start_year + 1),
  CONSTRAINT chk_distinct_relegated 
    CHECK (
      (relegated_team_1 IS NULL OR relegated_team_2 IS NULL OR relegated_team_1 <> relegated_team_2)
      AND (relegated_team_1 IS NULL OR relegated_team_3 IS NULL OR relegated_team_1 <> relegated_team_3)
      AND (relegated_team_2 IS NULL OR relegated_team_3 IS NULL OR relegated_team_2 <> relegated_team_3)
    )
);
COMMENT ON TABLE "Seasons" IS 'Information about specific seasons of leagues. CHECK (end_year = start_year + 1)';
COMMENT ON COLUMN "Seasons"."created_at" IS 'Record creation timestamp';

-- FK
ALTER TABLE "Seasons" ADD FOREIGN KEY ("league_id") REFERENCES "Leagues" ("id") ON DELETE CASCADE ON UPDATE CASCADE;
-- Champion/Relegated: ON DELETE SET NULL để không phá Season nếu team bị xóa (thực tế hiếm)
ALTER TABLE "Seasons" ADD FOREIGN KEY ("champion_team_id") REFERENCES "Teams" ("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "Seasons" ADD FOREIGN KEY ("relegated_team_1") REFERENCES "Teams" ("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "Seasons" ADD FOREIGN KEY ("relegated_team_2") REFERENCES "Teams" ("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "Seasons" ADD FOREIGN KEY ("relegated_team_3") REFERENCES "Teams" ("id") ON DELETE SET NULL ON UPDATE CASCADE;
CREATE UNIQUE INDEX ON "Seasons" ("league_id", "name");

-- 5. Bảng Stadiums
CREATE TABLE "Stadiums" (
  "id" SERIAL PRIMARY KEY,
  "name" VARCHAR(255) UNIQUE NOT NULL,
  "city" VARCHAR(100),
  "capacity" INT CHECK (capacity >= 0),
  "timezone" VARCHAR(50),  -- Nên lưu chuẩn TZ database name (ví dụ 'Europe/London'), ETL chuyển match_datetime đúng
  "created_at" TIMESTAMP NOT NULL DEFAULT now(),
  "updated_at" TIMESTAMP NOT NULL DEFAULT now()
);
COMMENT ON TABLE "Stadiums" IS 'Information about stadiums.';
COMMENT ON COLUMN "Stadiums"."timezone" IS 'Timezone of stadium, helpful for converting match datetime';
COMMENT ON COLUMN "Stadiums"."created_at" IS 'Record creation timestamp';
COMMENT ON COLUMN "Stadiums"."updated_at" IS 'When this record was last updated';

-- 6. Bảng Teams
CREATE TABLE "Teams" (
  "id" SERIAL PRIMARY KEY,
  "name" VARCHAR(255) UNIQUE NOT NULL,
  "short_name" VARCHAR(50) UNIQUE,
  "stadium_id" INT NULL,
  "established_year" INT CHECK (established_year > 1800 AND established_year <= EXTRACT(YEAR FROM NOW())::INT),
  "logo_url" VARCHAR(255),
  "created_at" TIMESTAMP NOT NULL DEFAULT now(),
  "updated_at" TIMESTAMP NOT NULL DEFAULT now()
);
COMMENT ON TABLE "Teams" IS 'Information about football teams.';
COMMENT ON COLUMN "Teams"."created_at" IS 'Record creation timestamp';
COMMENT ON COLUMN "Teams"."updated_at" IS 'When this record was last updated';

ALTER TABLE "Teams" ADD FOREIGN KEY ("stadium_id") REFERENCES "Stadiums" ("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- 7. Bảng Referees
CREATE TABLE "Referees" (
  "id" SERIAL PRIMARY KEY,
  "name" VARCHAR(255) NOT NULL,
  "date_of_birth" DATE,
  "country" VARCHAR(100),
  "created_at" TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_referee_name_dob UNIQUE ("name", "date_of_birth")
);
COMMENT ON TABLE "Referees" IS 'Information about football referees.';
COMMENT ON COLUMN "Referees"."created_at" IS 'Record creation timestamp';

-- 8. Bảng Players
CREATE TABLE "Players" (
  "id" SERIAL PRIMARY KEY,
  "name" VARCHAR(255) NOT NULL,
  "position" VARCHAR(50),  -- ví dụ 'GK','DEF','MID','FWD' hoặc chi tiết hơn
  "date_of_birth" DATE,
  "nationality" VARCHAR(100),
  "height" INT CHECK (height >= 0),
  "created_at" TIMESTAMP NOT NULL DEFAULT now(),
  "updated_at" TIMESTAMP NOT NULL DEFAULT now()
);
COMMENT ON TABLE "Players" IS 'Information about football players.';
COMMENT ON COLUMN "Players"."created_at" IS 'Record creation timestamp';
COMMENT ON COLUMN "Players"."updated_at" IS 'When this record was last updated';

-- 9. Bảng Matches
CREATE TABLE "Matches" (
  "id" SERIAL PRIMARY KEY,
  "season_id" INT NOT NULL,
  "match_datetime" TIMESTAMP NOT NULL,
  "match_week" VARCHAR(16),
  "home_team_id" INT NOT NULL,
  "away_team_id" INT NOT NULL,
  "stadium_id" INT,
  "referee_id" INT,
  "home_goals" INT CHECK (home_goals >= 0) ,
  "away_goals" INT CHECK (away_goals >= 0),
  "half_time_home_goals" INT CHECK (half_time_home_goals >= 0),
  "half_time_away_goals" INT CHECK (half_time_away_goals >= 0),
  "outcome" MatchOutcome,  -- NULL nếu match chưa FINISHED
  "status" MatchStatus NOT NULL,
  "created_at" TIMESTAMP NOT NULL DEFAULT now(),
  "updated_at" TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT chk_diff_teams CHECK (home_team_id <> away_team_id),
  CONSTRAINT chk_outcome_if_finished CHECK (
    (status = 'FINISHED' AND outcome IN ('H','D','A')) OR
    (status <> 'FINISHED' AND outcome IS NULL)
  )
);
COMMENT ON TABLE "Matches" IS 'Details of individual football matches. CHECK (home_team_id <> away_team_id)';
COMMENT ON COLUMN "Matches"."home_goals" IS 'NULL nếu match chưa FINISHED. CHECK >= 0';
COMMENT ON COLUMN "Matches"."away_goals" IS 'NULL nếu match chưa FINISHED. CHECK >= 0';
COMMENT ON COLUMN "Matches"."half_time_home_goals" IS 'NULL nếu match chưa FINISHED hoặc HT score not available. CHECK >= 0';
COMMENT ON COLUMN "Matches"."half_time_away_goals" IS 'NULL nếu match chưa FINISHED hoặc HT score not available. CHECK >= 0';
COMMENT ON COLUMN "Matches"."outcome" IS 'NULL nếu match chưa FINISHED (H: Home, D: Draw, A: Away)';
COMMENT ON COLUMN "Matches"."created_at" IS 'Record creation timestamp';
COMMENT ON COLUMN "Matches"."updated_at" IS 'When this record was last updated';

-- FK Matches
ALTER TABLE "Matches" ADD FOREIGN KEY ("season_id") REFERENCES "Seasons" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "Matches" ADD FOREIGN KEY ("home_team_id") REFERENCES "Teams" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "Matches" ADD FOREIGN KEY ("away_team_id") REFERENCES "Teams" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "Matches" ADD FOREIGN KEY ("stadium_id") REFERENCES "Stadiums" ("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "Matches" ADD FOREIGN KEY ("referee_id") REFERENCES "Referees" ("id") ON DELETE SET NULL ON UPDATE CASCADE;

CREATE INDEX ON "Matches" ("season_id", "match_datetime");
CREATE INDEX ON "Matches" ("home_team_id", "away_team_id");
CREATE INDEX ON "Matches" ("home_team_id", "match_datetime");
CREATE INDEX ON "Matches" ("away_team_id", "match_datetime");
CREATE INDEX ON "Matches" ("match_datetime");

-- 10. Bảng MatchEvents
CREATE TABLE "MatchEvents" (
  "id" SERIAL PRIMARY KEY,
  "match_id" INT NOT NULL,
  "minute" INT CHECK (minute >= 0),
  "event_type" MatchEventType NOT NULL,
  "team_id" INT,
  "player_id" INT,
  "related_player_id" INT,
  "period" MatchPeriod NOT NULL,
  "description" VARCHAR(500),
  "created_at" TIMESTAMP NOT NULL DEFAULT now(),
  "updated_at" TIMESTAMP NOT NULL DEFAULT now()
);
COMMENT ON TABLE "MatchEvents" IS 'Detailed events that occurred during a match (goals, cards, etc.).';
COMMENT ON COLUMN "MatchEvents"."minute" IS 'Minute of the event. CHECK >= 0';
COMMENT ON COLUMN "MatchEvents"."created_at" IS 'Record creation timestamp';
COMMENT ON COLUMN "MatchEvents"."updated_at" IS 'When this record was last updated';

-- FK MatchEvents
ALTER TABLE "MatchEvents" ADD FOREIGN KEY ("match_id") REFERENCES "Matches" ("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "MatchEvents" ADD FOREIGN KEY ("team_id") REFERENCES "Teams" ("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "MatchEvents" ADD FOREIGN KEY ("player_id") REFERENCES "Players" ("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "MatchEvents" ADD FOREIGN KEY ("related_player_id") REFERENCES "Players" ("id") ON DELETE SET NULL ON UPDATE CASCADE;

CREATE INDEX ON "MatchEvents" ("match_id");
CREATE INDEX ON "MatchEvents" ("event_type");
CREATE INDEX ON "MatchEvents" ("player_id");

-- 11. Bảng MatchPlayerStats
CREATE TABLE "MatchPlayerStats" (
  "id" SERIAL PRIMARY KEY,
  "match_id" INT NOT NULL,
  "team_id" INT NOT NULL,
  "player_id" INT NOT NULL,
  "is_starter" BOOLEAN NOT NULL DEFAULT FALSE,
  "minutes_played" INT NOT NULL CHECK (minutes_played >= 0),
  "goals" INT NOT NULL DEFAULT 0 CHECK (goals >= 0),
  "assists" INT NOT NULL DEFAULT 0 CHECK (assists >= 0),
  "shots" INT NOT NULL DEFAULT 0 CHECK (shots >= 0),
  "shots_on_target" INT NOT NULL DEFAULT 0 CHECK (shots_on_target >= 0),
  "passes" INT NOT NULL DEFAULT 0 CHECK (passes >= 0),
  "accurate_passes" INT NOT NULL DEFAULT 0 CHECK (accurate_passes >= 0),
  "key_passes" INT NOT NULL DEFAULT 0 CHECK (key_passes >= 0),
  "tackles" INT NOT NULL DEFAULT 0 CHECK (tackles >= 0),
  "interceptions" INT NOT NULL DEFAULT 0 CHECK (interceptions >= 0),
  "fouls_committed" INT NOT NULL DEFAULT 0 CHECK (fouls_committed >= 0),
  "fouls_drawn" INT NOT NULL DEFAULT 0 CHECK (fouls_drawn >= 0),
  "yellow_cards" INT NOT NULL DEFAULT 0 CHECK (yellow_cards >= 0),
  "red_cards" INT NOT NULL DEFAULT 0 CHECK (red_cards >= 0),
  "saves" INT NOT NULL DEFAULT 0 CHECK (saves >= 0),
  "substituted_in_minute" INT CHECK (substituted_in_minute >= 0),
  "substituted_out_minute" INT CHECK (substituted_out_minute >= 0),
  "created_at" TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_match_player UNIQUE ("match_id", "player_id"),
  CONSTRAINT chk_accurate_le_passes CHECK (accurate_passes <= passes)
);
COMMENT ON TABLE "MatchPlayerStats" IS 'Player-specific statistics for a single match.';
COMMENT ON COLUMN "MatchPlayerStats"."minutes_played" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchPlayerStats"."goals" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchPlayerStats"."assists" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchPlayerStats"."shots" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchPlayerStats"."shots_on_target" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchPlayerStats"."passes" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchPlayerStats"."accurate_passes" IS 'CHECK >= 0. CHECK accurate_passes <= passes';
COMMENT ON COLUMN "MatchPlayerStats"."key_passes" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchPlayerStats"."tackles" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchPlayerStats"."interceptions" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchPlayerStats"."fouls_committed" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchPlayerStats"."fouls_drawn" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchPlayerStats"."yellow_cards" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchPlayerStats"."red_cards" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchPlayerStats"."saves" IS 'For Goalkeepers. CHECK >= 0';
COMMENT ON COLUMN "MatchPlayerStats"."created_at" IS 'Record creation timestamp';

-- FK MatchPlayerStats
ALTER TABLE "MatchPlayerStats" ADD FOREIGN KEY ("match_id") REFERENCES "Matches" ("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "MatchPlayerStats" ADD FOREIGN KEY ("team_id") REFERENCES "Teams" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "MatchPlayerStats" ADD FOREIGN KEY ("player_id") REFERENCES "Players" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE INDEX ON "MatchPlayerStats" ("match_id", "team_id");
CREATE INDEX ON "MatchPlayerStats" ("player_id");

-- 12. Bảng MatchTeamStats
CREATE TABLE "MatchTeamStats" (
  "id" SERIAL PRIMARY KEY,
  "match_id" INT NOT NULL,
  "team_id" INT NOT NULL,
  "possession_percentage" NUMERIC(5,2) CHECK (possession_percentage >= 0 AND possession_percentage <= 100),
  "total_shots" INT NOT NULL DEFAULT 0 CHECK (total_shots >= 0),
  "shots_on_target" INT NOT NULL DEFAULT 0 CHECK (shots_on_target >= 0),
  "shots_off_target" INT NOT NULL DEFAULT 0 CHECK (shots_off_target >= 0),
  "blocked_shots" INT NOT NULL DEFAULT 0 CHECK (blocked_shots >= 0),
  "fouls_committed" INT NOT NULL DEFAULT 0 CHECK (fouls_committed >= 0),
  "corners" INT NOT NULL DEFAULT 0 CHECK (corners >= 0),
  "offsides" INT NOT NULL DEFAULT 0 CHECK (offsides >= 0),
  "yellow_cards" INT NOT NULL DEFAULT 0 CHECK (yellow_cards >= 0),
  "red_cards" INT NOT NULL DEFAULT 0 CHECK (red_cards >= 0),
  "saves" INT NOT NULL DEFAULT 0 CHECK (saves >= 0),
  "created_at" TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_match_team UNIQUE ("match_id", "team_id")
);
COMMENT ON TABLE "MatchTeamStats" IS 'Team-specific statistics for a single match (home or away team).';
COMMENT ON COLUMN "MatchTeamStats"."possession_percentage" IS 'CHECK 0 to 100';
COMMENT ON COLUMN "MatchTeamStats"."total_shots" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchTeamStats"."shots_on_target" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchTeamStats"."shots_off_target" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchTeamStats"."blocked_shots" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchTeamStats"."fouls_committed" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchTeamStats"."corners" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchTeamStats"."offsides" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchTeamStats"."yellow_cards" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchTeamStats"."red_cards" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchTeamStats"."saves" IS 'CHECK >= 0';
COMMENT ON COLUMN "MatchTeamStats"."created_at" IS 'Record creation timestamp';

-- FK MatchTeamStats
ALTER TABLE "MatchTeamStats" ADD FOREIGN KEY ("match_id") REFERENCES "Matches" ("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "MatchTeamStats" ADD FOREIGN KEY ("team_id") REFERENCES "Teams" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE INDEX ON "MatchTeamStats" ("match_id");
CREATE INDEX ON "MatchTeamStats" ("team_id");

-- 13. Bảng SquadAvailability
CREATE TABLE "SquadAvailability" (
  "id" SERIAL PRIMARY KEY,
  "match_id" INT NOT NULL,
  "team_id" INT NOT NULL,
  "player_id" INT NOT NULL,
  "status" PlayerStatus NOT NULL,
  "notes" VARCHAR(500),
  "updated_at" TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_sq_avail UNIQUE ("match_id", "team_id", "player_id")
);
COMMENT ON TABLE "SquadAvailability" IS 'Records player availability status (injured, suspended, etc.) for a specific match.';
COMMENT ON COLUMN "SquadAvailability"."updated_at" IS 'Timestamp when this status was recorded/updated';

-- FK SquadAvailability
ALTER TABLE "SquadAvailability" ADD FOREIGN KEY ("match_id") REFERENCES "Matches" ("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "SquadAvailability" ADD FOREIGN KEY ("team_id") REFERENCES "Teams" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "SquadAvailability" ADD FOREIGN KEY ("player_id") REFERENCES "Players" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE INDEX ON "SquadAvailability" ("match_id", "team_id");

-- 14. Bảng Lineups
CREATE TABLE "Lineups" (
  "id" SERIAL PRIMARY KEY,
  "match_id" INT NOT NULL,
  "team_id" INT NOT NULL,
  "player_id" INT NOT NULL,
  "is_starter" BOOLEAN NOT NULL DEFAULT FALSE,
  "position_in_lineup" VARCHAR(50),  -- đủ dài cho mô tả chi tiết
  "shirt_number" INT CHECK (shirt_number >= 0),
  "is_captain" BOOLEAN NOT NULL DEFAULT FALSE,
  "reported_at" TIMESTAMP NOT NULL,
  "created_at" TIMESTAMP NOT NULL DEFAULT now(),
  "updated_at" TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_lineup UNIQUE ("match_id", "team_id", "player_id")
);
COMMENT ON TABLE "Lineups" IS 'Records the starting lineup and substitutes for each team in a match as reported before kickoff.';
COMMENT ON COLUMN "Lineups"."match_id" IS 'References Matches table';
COMMENT ON COLUMN "Lineups"."position_in_lineup" IS 'Optional, tactical position (e.g., GK, CB, LW). VARCHAR(50) đủ linh hoạt.';
COMMENT ON COLUMN "Lineups"."reported_at" IS 'When this lineup information was officially reported/recorded (~1 hour before kickoff)';
COMMENT ON COLUMN "Lineups"."created_at" IS 'Record creation timestamp';
COMMENT ON COLUMN "Lineups"."updated_at" IS 'When this record was last updated';

-- FK Lineups
ALTER TABLE "Lineups" ADD FOREIGN KEY ("match_id") REFERENCES "Matches" ("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "Lineups" ADD FOREIGN KEY ("team_id") REFERENCES "Teams" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "Lineups" ADD FOREIGN KEY ("player_id") REFERENCES "Players" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE INDEX ON "Lineups" ("match_id", "team_id");
CREATE INDEX ON "Lineups" ("player_id");

-- 15. Bảng TeamSeasonLocationStats
CREATE TABLE "TeamSeasonLocationStats" (
  "id" SERIAL PRIMARY KEY,
  "team_id" INT NOT NULL,
  "season_id" INT NOT NULL,
  "match_date_ref" DATE NOT NULL,  -- stats tính đến ngày này (trước hoặc bằng)
  "location" LocationType NOT NULL,
  "matches_played" INT NOT NULL DEFAULT 0 CHECK (matches_played >= 0),
  "wins" INT NOT NULL DEFAULT 0 CHECK (wins >= 0),
  "draws" INT NOT NULL DEFAULT 0 CHECK (draws >= 0),
  "losses" INT NOT NULL DEFAULT 0 CHECK (losses >= 0),
  "goals_for" INT NOT NULL DEFAULT 0 CHECK (goals_for >= 0),
  "goals_against" INT NOT NULL DEFAULT 0 CHECK (goals_against >= 0),
  "clean_sheets" INT NOT NULL DEFAULT 0 CHECK (clean_sheets >= 0),
  "failed_to_score" INT NOT NULL DEFAULT 0 CHECK (failed_to_score >= 0),
  "points" INT NOT NULL DEFAULT 0 CHECK (points >= 0),
  "avg_goals_for" NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (avg_goals_for >= 0),
  "avg_goals_against" NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (avg_goals_against >= 0),
  "win_rate" NUMERIC(5,4) NOT NULL DEFAULT 0 CHECK (win_rate >= 0 AND win_rate <= 1),
  "draw_rate" NUMERIC(5,4) NOT NULL DEFAULT 0 CHECK (draw_rate >= 0 AND draw_rate <= 1),
  "loss_rate" NUMERIC(5,4) NOT NULL DEFAULT 0 CHECK (loss_rate >= 0 AND loss_rate <= 1),
  "goal_difference" INT NOT NULL,
  "avg_possession_percentage" NUMERIC(5,2) CHECK (avg_possession_percentage >= 0 AND avg_possession_percentage <= 100),
  "avg_total_shots" NUMERIC(7,2) CHECK (avg_total_shots >= 0),
  "avg_shots_on_target" NUMERIC(7,2) CHECK (avg_shots_on_target >= 0),
  "generated_at" TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_team_season_location_ref UNIQUE ("team_id", "season_id", "location", "match_date_ref")
);
COMMENT ON TABLE "TeamSeasonLocationStats" IS 'Pre-calculated season-level stats for teams, filtered by date and location.';
COMMENT ON COLUMN "TeamSeasonLocationStats"."match_date_ref" IS 'Stats calculated using matches BEFORE or ON this date';
COMMENT ON COLUMN "TeamSeasonLocationStats"."location" IS '''Home'', ''Away'', hoặc ''Overall''';

-- FK TeamSeasonLocationStats
ALTER TABLE "TeamSeasonLocationStats" ADD FOREIGN KEY ("team_id") REFERENCES "Teams" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "TeamSeasonLocationStats" ADD FOREIGN KEY ("season_id") REFERENCES "Seasons" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE INDEX ON "TeamSeasonLocationStats" ("match_date_ref");

-- 16. Bảng TeamFormStats
CREATE TABLE "TeamFormStats" (
  "id" SERIAL PRIMARY KEY,
  "team_id" INT NOT NULL,
  "match_date_ref" DATE NOT NULL,
  "num_matches" INT NOT NULL CHECK (num_matches > 0),
  "location_context" LocationType NOT NULL,  -- Home/Away/Overall
  "wins" INT NOT NULL DEFAULT 0 CHECK (wins >= 0),
  "draws" INT NOT NULL DEFAULT 0 CHECK (draws >= 0),
  "losses" INT NOT NULL DEFAULT 0 CHECK (losses >= 0),
  "goals_for" INT NOT NULL DEFAULT 0 CHECK (goals_for >= 0),
  "goals_against" INT NOT NULL DEFAULT 0 CHECK (goals_against >= 0),
  "clean_sheets" INT NOT NULL DEFAULT 0 CHECK (clean_sheets >= 0),
  "failed_to_score" INT NOT NULL DEFAULT 0 CHECK (failed_to_score >= 0),
  "points" INT NOT NULL DEFAULT 0 CHECK (points >= 0),
  "avg_goals_for" NUMERIC(6,2) NOT NULL DEFAULT 0 CHECK (avg_goals_for >= 0),
  "avg_goals_against" NUMERIC(6,2) NOT NULL DEFAULT 0 CHECK (avg_goals_against >= 0),
  "win_rate" NUMERIC(5,4) NOT NULL DEFAULT 0 CHECK (win_rate >= 0 AND win_rate <= 1),
  "draw_rate" NUMERIC(5,4) NOT NULL DEFAULT 0 CHECK (draw_rate >= 0 AND draw_rate <= 1),
  "loss_rate" NUMERIC(5,4) NOT NULL DEFAULT 0 CHECK (loss_rate >= 0 AND loss_rate <= 1),
  "goal_difference" INT NOT NULL,
  "avg_possession_percentage" NUMERIC(5,2) CHECK (avg_possession_percentage >= 0 AND avg_possession_percentage <= 100),
  "avg_total_shots" NUMERIC(7,2) CHECK (avg_total_shots >= 0),
  "avg_shots_on_target" NUMERIC(7,2) CHECK (avg_shots_on_target >= 0),
  "generated_at" TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_team_form UNIQUE ("team_id", "match_date_ref", "num_matches", "location_context")
);
COMMENT ON TABLE "TeamFormStats" IS 'Pre-calculated stats for team form over N recent matches.';
COMMENT ON COLUMN "TeamFormStats"."match_date_ref" IS 'Stats calculated using matches BEFORE or ON this date';

-- FK TeamFormStats
ALTER TABLE "TeamFormStats" ADD FOREIGN KEY ("team_id") REFERENCES "Teams" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE INDEX ON "TeamFormStats" ("match_date_ref");

-- 17. Bảng PlayerSeasonStats
CREATE TABLE "PlayerSeasonStats" (
  "id" SERIAL PRIMARY KEY,
  "player_id" INT NOT NULL,
  "team_id" INT NOT NULL,
  "season_id" INT NOT NULL,
  "match_date_ref" DATE NOT NULL,
  "appearances" INT NOT NULL DEFAULT 0 CHECK (appearances >= 0),
  "minutes_played" INT NOT NULL DEFAULT 0 CHECK (minutes_played >= 0),
  "goals" INT NOT NULL DEFAULT 0 CHECK (goals >= 0),
  "assists" INT NOT NULL DEFAULT 0 CHECK (assists >= 0),
  "yellow_cards" INT NOT NULL DEFAULT 0 CHECK (yellow_cards >= 0),
  "red_cards" INT NOT NULL DEFAULT 0 CHECK (red_cards >= 0),
  "shots" INT NOT NULL DEFAULT 0 CHECK (shots >= 0),
  "shots_on_target" INT NOT NULL DEFAULT 0 CHECK (shots_on_target >= 0),
  "goals_per_90_minutes" NUMERIC(6,2) NOT NULL DEFAULT 0 CHECK (goals_per_90_minutes >= 0),
  "assists_per_90_minutes" NUMERIC(6,2) NOT NULL DEFAULT 0 CHECK (assists_per_90_minutes >= 0),
  "generated_at" TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_player_season UNIQUE ("player_id", "team_id", "season_id", "match_date_ref")
);
COMMENT ON TABLE "PlayerSeasonStats" IS 'Pre-calculated season-level stats for players for a specific team within that season.';
COMMENT ON COLUMN "PlayerSeasonStats"."match_date_ref" IS 'Stats calculated using matches BEFORE or ON this date';

-- FK PlayerSeasonStats
ALTER TABLE "PlayerSeasonStats" ADD FOREIGN KEY ("player_id") REFERENCES "Players" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "PlayerSeasonStats" ADD FOREIGN KEY ("team_id") REFERENCES "Teams" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "PlayerSeasonStats" ADD FOREIGN KEY ("season_id") REFERENCES "Seasons" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE INDEX ON "PlayerSeasonStats" ("match_date_ref");

-- 18. Bảng BettingOdds
CREATE TABLE "BettingOdds" (
  "id" SERIAL PRIMARY KEY,
  "match_id" INT NOT NULL,
  "bookmaker_name" VARCHAR(255) NOT NULL,
  "home_win_odds" DECIMAL(10,2) CHECK (home_win_odds > 1.0),
  "draw_odds" DECIMAL(10,2) CHECK (draw_odds > 1.0),
  "away_win_odds" DECIMAL(10,2) CHECK (away_win_odds > 1.0),
  "snapshot_at" TIMESTAMP NOT NULL,
  CONSTRAINT uq_odds_snapshot UNIQUE ("match_id", "bookmaker_name", "snapshot_at")
);
COMMENT ON TABLE "BettingOdds" IS 'Betting odds data for matches from various bookmakers.';
COMMENT ON COLUMN "BettingOdds"."home_win_odds" IS 'CHECK > 1.0';
COMMENT ON COLUMN "BettingOdds"."draw_odds" IS 'CHECK > 1.0';
COMMENT ON COLUMN "BettingOdds"."away_win_odds" IS 'CHECK > 1.0';
COMMENT ON COLUMN "BettingOdds"."snapshot_at" IS 'Timestamp when the odds were recorded';

ALTER TABLE "BettingOdds" ADD FOREIGN KEY ("match_id") REFERENCES "Matches" ("id") ON DELETE CASCADE ON UPDATE CASCADE;
CREATE INDEX ON "BettingOdds" ("match_id", "snapshot_at");

-- 19. Bảng RefereeStats
CREATE TABLE "RefereeStats" (
  "id" SERIAL PRIMARY KEY,
  "referee_id" INT NOT NULL,
  "match_date_ref" DATE NOT NULL,
  "matches_officiated" INT NOT NULL DEFAULT 0 CHECK (matches_officiated >= 0),
  "avg_yellow_cards_per_match" DECIMAL(5,2) NOT NULL DEFAULT 0 CHECK (avg_yellow_cards_per_match >= 0),
  "avg_red_cards_per_match" DECIMAL(5,2) NOT NULL DEFAULT 0 CHECK (avg_red_cards_per_match >= 0),
  "avg_fouls_per_match" DECIMAL(5,2) NOT NULL DEFAULT 0 CHECK (avg_fouls_per_match >= 0),
  "penalty_awarded_rate" DECIMAL(5,4) NOT NULL DEFAULT 0 CHECK (penalty_awarded_rate >= 0 AND penalty_awarded_rate <= 1),
  "generated_at" TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_referee_stats UNIQUE ("referee_id", "match_date_ref")
);
COMMENT ON TABLE "RefereeStats" IS 'Pre-calculated stats for referees, filtered by date.';
COMMENT ON COLUMN "RefereeStats"."match_date_ref" IS 'Stats calculated using matches BEFORE or ON this date';

ALTER TABLE "RefereeStats" ADD FOREIGN KEY ("referee_id") REFERENCES "Referees" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;
CREATE INDEX ON "RefereeStats" ("match_date_ref");

-- 20. INDEXES (đã tạo kèm các bảng)
-- Đảm bảo các index trên FK và cột tham chiếu đã được tạo phía trên.

-- 21. MỘT SỐ LƯU Ý KHI DÙNG SCHEMA NÀY:
-- - Khi ETL dữ liệu, hãy đảm bảo time cutoff: aggregated stats tính trước ngày match_datetime (ví dụ match_date_ref = date(match_datetime) - 1).
-- - Với Seasons: champion/relegated để NULL cho đến khi season kết thúc.
-- - Với Matches.status: nếu dùng realtime, có thể thêm trạng thái IN_PROGRESS; ở đây giữ SCHEDULED/FINISHED đủ cho dữ liệu lịch sử.
-- - Với numeric fields: PostgreSQL NUMERIC(5,2)/(7,2) đủ cho hầu hết giá trị trung bình; nếu cần precision khác, điều chỉnh.
-- - Với name length: VARCHAR độ dài bạn có thể tùy chỉnh; ở đây giữ như cũ.
-- - ON DELETE/ON UPDATE: bạn có thể điều chỉnh tuỳ chính sách xóa record. Ở đây chọn RESTRICT hoặc SET NULL để tránh mất dữ liệu quan trọng.
-- - Với bảng aggregated: TeamSeasonLocationStats, TeamFormStats, PlayerSeasonStats, RefereeStats: script DDL tạo constraint nhưng ETL logic bạn tự viết trong Python/SQL để populate.
-- - Nếu không dùng một số bảng (Lineups, SquadAvailability, BettingOdds) vì không có dữ liệu, bạn có thể để trống hoặc drop sau; không ảnh hưởng schema chính.
-- - Khi load dữ liệu, kiểm tra ràng buộc (constraints) báo lỗi để điều chỉnh ETL: ví dụ season name trùng, đội duplicate, v.v.
-- - Nếu muốn thêm external_id/source để mapping dữ liệu từ API, bạn có thể ALTER TABLE thêm cột VARCHAR cho Teams, Players, Matches...
-- - Đảm bảo timezone: khi lưu match_datetime, chuẩn hóa về UTC hoặc timezone nhất quán; Stadiums.timezone giúp convert khi cần.
-- - Đặt triggers/nâng cấp: có thể thêm trigger tự động cập nhật updated_at = now() khi UPDATE record, nhưng không bắt buộc.

-- 22. Ví dụ trigger cập nhật updated_at (tùy chọn)
-- Ví dụ hàm và trigger để tự động set updated_at:
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ language 'plpgsql';

-- Áp dụng trigger cho các bảng có cột updated_at
DO $$
BEGIN
  -- MatchEvents
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_matchevents_updated_at'
  ) THEN
    CREATE TRIGGER trg_matchevents_updated_at
    BEFORE UPDATE ON "MatchEvents"
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
  END IF;
  -- Matches
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_matches_updated_at'
  ) THEN
    CREATE TRIGGER trg_matches_updated_at
    BEFORE UPDATE ON "Matches"
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
  END IF;
  -- Teams
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_teams_updated_at'
  ) THEN
    CREATE TRIGGER trg_teams_updated_at
    BEFORE UPDATE ON "Teams"
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
  END IF;
  -- Stadiums
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_stadiums_updated_at'
  ) THEN
    CREATE TRIGGER trg_stadiums_updated_at
    BEFORE UPDATE ON "Stadiums"
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
  END IF;
  -- Players
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_players_updated_at'
  ) THEN
    CREATE TRIGGER trg_players_updated_at
    BEFORE UPDATE ON "Players"
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
  END IF;
  -- Lineups
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_lineups_updated_at'
  ) THEN
    CREATE TRIGGER trg_lineups_updated_at
    BEFORE UPDATE ON "Lineups"
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
  END IF;
END;
$$;

-- Kết thúc DDL.
