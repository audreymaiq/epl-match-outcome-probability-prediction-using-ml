-- Migration 002: Add EloRatings table
-- Used by ml/elo/elo_builder.py to persist pre-match ELO for each team.
-- Run ONCE on an existing DB. Safe to re-run (uses IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS "EloRatings" (
    id         SERIAL PRIMARY KEY,
    team_id    INT    NOT NULL REFERENCES "Teams"(id) ON DELETE CASCADE ON UPDATE CASCADE,
    match_id   INT    NULL     REFERENCES "Matches"(id) ON DELETE SET NULL ON UPDATE CASCADE,
    match_date DATE   NOT NULL,
    elo_before FLOAT  NOT NULL,
    elo_after  FLOAT  NOT NULL,
    k_factor   FLOAT  NOT NULL DEFAULT 32.0,
    season     VARCHAR(10) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT uq_elo_team_match UNIQUE (team_id, match_date, match_id)
);

COMMENT ON TABLE  "EloRatings"           IS 'Stores pre- and post-match ELO ratings per team. elo_before is the value used as a feature (no leakage).';
COMMENT ON COLUMN "EloRatings".elo_before IS 'ELO rating BEFORE this match - the value used as a ML feature.';
COMMENT ON COLUMN "EloRatings".elo_after  IS 'ELO rating AFTER this match - used as elo_before for the next match.';
COMMENT ON COLUMN "EloRatings".k_factor   IS 'K-factor applied in this update (adaptive by match importance).';

CREATE INDEX IF NOT EXISTS idx_elo_team_date ON "EloRatings" (team_id, match_date);

-- Trigger to keep updated_at current
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_eloratings_updated_at'
    ) THEN
        CREATE TRIGGER trg_eloratings_updated_at
        BEFORE UPDATE ON "EloRatings"
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END;
$$;

