-- Migration 005: Reconcile feature store tables
-- The init-db.sql created older versions of feature tables (keyed by match_date_ref).
-- Migration 004 uses IF NOT EXISTS, which skips if old tables exist.
-- This migration drops the old tables and re-creates them in the correct schema.
-- IMPORTANT: Only run this if you have NOT populated migration-004-style tables.
-- If you have production data, back up first.

-- ────────────────────────────────────────────────────────────────────────────────
-- Step 1: Drop old feature tables that use match_date_ref (from init-db.sql)
-- These conflict with the match_id-keyed tables from migration 004.
-- ────────────────────────────────────────────────────────────────────────────────

-- Drop old TeamFormStats (init-db.sql version: keyed by team_id + match_date_ref + num_matches)
DROP TABLE IF EXISTS "TeamFormStats" CASCADE;

-- Drop old HeadToHeadStats (init-db.sql version: keyed by home_team_id + away_team_id + match_date_ref)
DROP TABLE IF EXISTS "HeadToHeadStats" CASCADE;

-- Drop old RefereeStats (init-db.sql version: keyed by referee_id + match_date_ref)
DROP TABLE IF EXISTS "RefereeStats" CASCADE;

-- TeamSeasonLocationStats from init-db.sql is keyed by (team_id, season_id, location, match_date_ref)
-- Migration 004 version is keyed by (match_id, team_id, location) - per-match snapshots
DROP TABLE IF EXISTS "TeamSeasonLocationStats" CASCADE;

-- Predictions may or may not exist
DROP TABLE IF EXISTS "Predictions" CASCADE;

-- BettingOdds from init-db.sql has different column names than migration 004
DROP TABLE IF EXISTS "BettingOdds" CASCADE;

-- ────────────────────────────────────────────────────────────────────────────────
-- Step 2: Re-create all feature tables (migration-004 schema, per-match snapshots)
-- ────────────────────────────────────────────────────────────────────────────────

-- TeamFormStats: rolling form stats per (match, team), computed BEFORE match_datetime
CREATE TABLE "TeamFormStats" (
    id                    SERIAL PRIMARY KEY,
    match_id              INT NOT NULL REFERENCES "Matches"(id) ON DELETE CASCADE,
    team_id               INT NOT NULL REFERENCES "Teams"(id)   ON DELETE CASCADE,
    season_id             INT          REFERENCES "Seasons"(id)  ON DELETE SET NULL,

    -- Last 5 matches
    form5_matches_played  INT          NOT NULL DEFAULT 0,
    form5_wins            INT          NOT NULL DEFAULT 0,
    form5_draws           INT          NOT NULL DEFAULT 0,
    form5_losses          INT          NOT NULL DEFAULT 0,
    form5_goals_scored    INT          NOT NULL DEFAULT 0,
    form5_goals_conceded  INT          NOT NULL DEFAULT 0,
    form5_avg_scored      NUMERIC(5,3) NOT NULL DEFAULT 0,
    form5_avg_conceded    NUMERIC(5,3) NOT NULL DEFAULT 0,
    form5_ppg             NUMERIC(5,3) NOT NULL DEFAULT 0,
    form5_clean_sheets    INT          NOT NULL DEFAULT 0,

    -- Last 10 matches
    form10_wins           INT          NOT NULL DEFAULT 0,
    form10_draws          INT          NOT NULL DEFAULT 0,
    form10_losses         INT          NOT NULL DEFAULT 0,
    form10_avg_scored     NUMERIC(5,3) NOT NULL DEFAULT 0,
    form10_avg_conceded   NUMERIC(5,3) NOT NULL DEFAULT 0,
    form10_ppg            NUMERIC(5,3) NOT NULL DEFAULT 0,

    computed_at           TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT uq_form_match_team UNIQUE (match_id, team_id)
);

COMMENT ON TABLE "TeamFormStats" IS
    'Pre-computed rolling form stats per (match, team). All stats are BEFORE match_datetime (no leakage).';

CREATE INDEX IF NOT EXISTS idx_form_team_match ON "TeamFormStats" (team_id, match_id);


-- TeamSeasonLocationStats: cumulative season stats per (match, team, location)
CREATE TABLE "TeamSeasonLocationStats" (
    id               SERIAL PRIMARY KEY,
    match_id         INT NOT NULL REFERENCES "Matches"(id)  ON DELETE CASCADE,
    team_id          INT NOT NULL REFERENCES "Teams"(id)    ON DELETE CASCADE,
    season_id        INT          REFERENCES "Seasons"(id)  ON DELETE SET NULL,
    location         "LocationType" NOT NULL,

    matches_played   INT          NOT NULL DEFAULT 0,
    wins             INT          NOT NULL DEFAULT 0,
    draws            INT          NOT NULL DEFAULT 0,
    losses           INT          NOT NULL DEFAULT 0,
    goals_scored     INT          NOT NULL DEFAULT 0,
    goals_conceded   INT          NOT NULL DEFAULT 0,
    points           INT          NOT NULL DEFAULT 0,
    ppg              NUMERIC(6,4) NOT NULL DEFAULT 0,
    clean_sheets     INT          NOT NULL DEFAULT 0,
    failed_to_score  INT          NOT NULL DEFAULT 0,

    computed_at      TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT uq_season_loc_match_team_loc UNIQUE (match_id, team_id, location)
);

COMMENT ON TABLE "TeamSeasonLocationStats" IS
    'Cumulative season stats per (match, team, location). All stats BEFORE match_datetime.';

CREATE INDEX IF NOT EXISTS idx_seasonloc_team ON "TeamSeasonLocationStats" (team_id, season_id);


-- HeadToHeadStats: all-time H2H stats as of each match
CREATE TABLE "HeadToHeadStats" (
    id              SERIAL PRIMARY KEY,
    match_id        INT NOT NULL REFERENCES "Matches"(id) ON DELETE CASCADE,
    home_team_id    INT NOT NULL REFERENCES "Teams"(id)   ON DELETE CASCADE,
    away_team_id    INT NOT NULL REFERENCES "Teams"(id)   ON DELETE CASCADE,

    total_meetings  INT          NOT NULL DEFAULT 0,
    home_wins       INT          NOT NULL DEFAULT 0,
    draws           INT          NOT NULL DEFAULT 0,
    away_wins       INT          NOT NULL DEFAULT 0,
    avg_home_goals  NUMERIC(5,3) NOT NULL DEFAULT 0,
    avg_away_goals  NUMERIC(5,3) NOT NULL DEFAULT 0,
    over_2_5_rate   NUMERIC(5,3) NOT NULL DEFAULT 0,
    btts_rate       NUMERIC(5,3) NOT NULL DEFAULT 0,

    computed_at     TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT uq_h2h_match UNIQUE (match_id)
);

COMMENT ON TABLE "HeadToHeadStats" IS
    'All-time H2H stats as of each match (BEFORE match_datetime, no leakage).';


-- RefereeStats: historical referee stats as of each match
CREATE TABLE "RefereeStats" (
    id                 SERIAL PRIMARY KEY,
    match_id           INT NOT NULL REFERENCES "Matches"(id)   ON DELETE CASCADE,
    referee_id         INT NOT NULL REFERENCES "Referees"(id)  ON DELETE CASCADE,

    games_officiated   INT          NOT NULL DEFAULT 0,
    avg_yellow_cards   NUMERIC(5,3) NOT NULL DEFAULT 0,
    avg_red_cards      NUMERIC(5,3) NOT NULL DEFAULT 0,
    home_win_rate      NUMERIC(5,4) NOT NULL DEFAULT 0,
    draw_rate          NUMERIC(5,4) NOT NULL DEFAULT 0,

    computed_at        TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT uq_ref_match_ref UNIQUE (match_id, referee_id)
);

COMMENT ON TABLE "RefereeStats" IS
    'Historical referee stats as of each match (BEFORE match_datetime).';


-- BettingOdds: pre-match betting odds and implied probabilities
CREATE TABLE "BettingOdds" (
    id              SERIAL PRIMARY KEY,
    match_id        INT          NOT NULL REFERENCES "Matches"(id) ON DELETE CASCADE,
    bookmaker       VARCHAR(100) NOT NULL,
    market          VARCHAR(50)  NOT NULL,
    home_odds       NUMERIC(7,3),
    draw_odds       NUMERIC(7,3),
    away_odds       NUMERIC(7,3),
    home_implied_prob NUMERIC(5,4),
    draw_implied_prob NUMERIC(5,4),
    away_implied_prob NUMERIC(5,4),
    recorded_at     TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT uq_odds_match_bk_mkt UNIQUE (match_id, bookmaker, market)
);

COMMENT ON TABLE "BettingOdds" IS
    'Pre-match betting odds and implied probabilities. Strong ML signal if available.';


-- Predictions: model predictions for monitoring
CREATE TABLE "Predictions" (
    id               SERIAL PRIMARY KEY,
    match_id         INT          NOT NULL REFERENCES "Matches"(id) ON DELETE CASCADE,
    model_version    VARCHAR(50)  NOT NULL,
    predicted_outcome VARCHAR(1)  NOT NULL CHECK (predicted_outcome IN ('H', 'D', 'A')),
    home_win_prob    NUMERIC(6,4) NOT NULL,
    draw_prob        NUMERIC(6,4) NOT NULL,
    away_win_prob    NUMERIC(6,4) NOT NULL,
    confidence       NUMERIC(6,4) NOT NULL,
    actual_outcome   VARCHAR(1)   CHECK (actual_outcome IN ('H', 'D', 'A')),
    was_correct      BOOLEAN,
    created_at       TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT uq_prediction_match_model UNIQUE (match_id, model_version)
);

COMMENT ON TABLE "Predictions" IS
    'Stores model predictions for monitoring accuracy over time.';

CREATE INDEX IF NOT EXISTS idx_predictions_match   ON "Predictions" (match_id);
CREATE INDEX IF NOT EXISTS idx_predictions_version ON "Predictions" (model_version);

