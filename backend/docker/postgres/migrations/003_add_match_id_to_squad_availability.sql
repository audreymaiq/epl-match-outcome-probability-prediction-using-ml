-- Migration 003: Add match_id to SquadAvailability
-- Allows querying which players were unavailable FOR A SPECIFIC MATCH
-- (used by ml/features/feature_extractor.py _fetch_absences()).
-- Run ONCE on existing DB.

ALTER TABLE "SquadAvailability"
    ADD COLUMN IF NOT EXISTS match_id INT NULL
        REFERENCES "Matches"(id) ON DELETE SET NULL ON UPDATE CASCADE;

COMMENT ON COLUMN "SquadAvailability".match_id IS
    'The specific match this availability record applies to. NULL = general unavailability window.';

CREATE INDEX IF NOT EXISTS idx_squad_avail_match ON "SquadAvailability" (match_id);
CREATE INDEX IF NOT EXISTS idx_squad_avail_team_match ON "SquadAvailability" (team_id, match_id);

