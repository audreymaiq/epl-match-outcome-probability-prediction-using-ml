-- Align raw match tables with the fields written by MatchLoader.
-- Safe to apply to a database created before this migration.

ALTER TABLE "Leagues"
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT now();

ALTER TABLE "Stadiums"
    ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;

ALTER TABLE "Matches"
    ADD COLUMN IF NOT EXISTS attendance INT CHECK (attendance >= 0);

ALTER TABLE "MatchPlayerStats"
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT now();

ALTER TABLE "MatchTeamStats"
    ADD COLUMN IF NOT EXISTS location "LocationType",
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT now();

-- The provider does not supply the time at which lineups were announced.
-- Unknown is represented by NULL, never by a fabricated pre-match timestamp.
ALTER TABLE "Lineups" ALTER COLUMN reported_at DROP NOT NULL;

-- Season IDs are mapped through this table just like other provider IDs.
DO $$
DECLARE
    old_constraint record;
BEGIN
    FOR old_constraint IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = '"ExternalMapping"'::regclass
          AND contype = 'c'
          AND pg_get_constraintdef(oid) LIKE '%entity_type%'
    LOOP
        EXECUTE format('ALTER TABLE "ExternalMapping" DROP CONSTRAINT %I', old_constraint.conname);
    END LOOP;
END;
$$;

ALTER TABLE "ExternalMapping"
    ADD CONSTRAINT chk_external_mapping_entity_type
    CHECK (entity_type IN ('team', 'player', 'match', 'stadium', 'league', 'season', 'referee'));
