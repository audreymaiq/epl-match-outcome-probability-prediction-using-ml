ALTER TABLE "EloRatings" ADD COLUMN league_id INT REFERENCES "Leagues"(id);
UPDATE "EloRatings" e SET league_id = s.league_id
FROM "Matches" m JOIN "Seasons" s ON s.id = m.season_id WHERE e.match_id = m.id;
ALTER TABLE "EloRatings" ADD COLUMN config_hash TEXT;
CREATE INDEX elo_scope_lookup ON "EloRatings"(league_id, team_id, match_date);

CREATE TABLE "FeatureBuilds" (
  league_id INT PRIMARY KEY REFERENCES "Leagues"(id),
  config_hash TEXT NOT NULL,
  source_updated_at TIMESTAMP,
  source_match_count BIGINT NOT NULL,
  built_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE "PipelineRuns" (
  run_id UUID PRIMARY KEY,
  league_slug TEXT NOT NULL,
  command TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'INTERRUPTED')),
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  configuration JSONB NOT NULL,
  steps JSONB NOT NULL DEFAULT '{}',
  error TEXT
);
CREATE INDEX pipeline_runs_scope_time ON "PipelineRuns"(league_slug, started_at DESC);
CREATE TABLE "ModelDeployments" (
  league_slug TEXT PRIMARY KEY,
  model_version TEXT NOT NULL,
  previous_version TEXT,
  activated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE "IngestionSnapshots" (
  id BIGSERIAL PRIMARY KEY,
  match_id INT NOT NULL REFERENCES "Matches"(id) ON DELETE CASCADE,
  source_system VARCHAR(50) NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  content_hash TEXT NOT NULL,
  payload JSONB NOT NULL,
  UNIQUE(match_id, source_system, content_hash)
);
CREATE TABLE "SourceMatchState" (
  match_id INT NOT NULL REFERENCES "Matches"(id) ON DELETE CASCADE,
  source_system VARCHAR(50) NOT NULL,
  summary_hash TEXT NOT NULL,
  checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(match_id, source_system)
);
CREATE TABLE "AvailabilityObservations" (
  match_id INT NOT NULL REFERENCES "Matches"(id) ON DELETE CASCADE,
  team_id INT NOT NULL REFERENCES "Teams"(id),
  observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  absences INT NOT NULL CHECK(absences>=0),
  goalkeeper_absent BOOLEAN NOT NULL,
  PRIMARY KEY(match_id, team_id, observed_at)
);
