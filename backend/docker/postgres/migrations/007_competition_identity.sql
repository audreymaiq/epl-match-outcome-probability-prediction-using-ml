-- Add competition scope without deleting existing records.
ALTER TABLE "Leagues" ADD COLUMN IF NOT EXISTS slug VARCHAR(100);
UPDATE "Leagues" SET slug = 'epl'
WHERE slug IS NULL AND country = 'England' AND name = 'Premier League';
UPDATE "Leagues" SET slug = 'legacy_' || id WHERE slug IS NULL;
ALTER TABLE "Leagues" ALTER COLUMN slug SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS leagues_slug_unique ON "Leagues" (slug);
ALTER TABLE "Leagues" DROP CONSTRAINT IF EXISTS "Leagues_external_id_key";
ALTER TABLE "Leagues" DROP CONSTRAINT IF EXISTS "Leagues_name_key";
COMMENT ON COLUMN "Leagues".external_id IS 'Legacy value; new ingestion uses ExternalMapping';
ALTER TABLE "Seasons" DROP CONSTRAINT IF EXISTS "Seasons_name_key";
ALTER TABLE "Seasons" DROP CONSTRAINT IF EXISTS chk_season_years;
ALTER TABLE "Seasons" ADD CONSTRAINT chk_season_years CHECK (end_year >= start_year);
ALTER TABLE "Teams" DROP CONSTRAINT IF EXISTS "Teams_name_key";
ALTER TABLE "Teams" DROP CONSTRAINT IF EXISTS "Teams_short_name_key";
ALTER TABLE "Stadiums" DROP CONSTRAINT IF EXISTS "Stadiums_name_key";
ALTER TABLE "Matches" DROP CONSTRAINT IF EXISTS uq_match_unique;
ALTER TABLE "Matches" ADD CONSTRAINT uq_match_unique UNIQUE (season_id, match_datetime, home_team_id, away_team_id);

ALTER TABLE "ExternalMapping" ADD COLUMN IF NOT EXISTS scope VARCHAR(100) NOT NULL DEFAULT '';
UPDATE "ExternalMapping" e SET scope = s.league_id::text
FROM "Seasons" s WHERE e.entity_type = 'season' AND e.internal_id = s.id AND e.scope = '';
DO $$
DECLARE c RECORD;
BEGIN
  FOR c IN SELECT conname FROM pg_constraint
    WHERE conrelid = '"ExternalMapping"'::regclass AND contype = 'u'
  LOOP
    EXECUTE format('ALTER TABLE "ExternalMapping" DROP CONSTRAINT %I', c.conname);
  END LOOP;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS external_mapping_scoped_unique
ON "ExternalMapping" (external_id, entity_type, source_system, scope);

CREATE TABLE "IngestionObservations" (
  match_id INT PRIMARY KEY REFERENCES "Matches"(id) ON DELETE CASCADE,
  source_system VARCHAR(50) NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  content_hash TEXT NOT NULL,
  component_status JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS seasons_league_index ON "Seasons"(league_id);
