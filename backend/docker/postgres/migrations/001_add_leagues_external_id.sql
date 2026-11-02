-- Migration: Add external_id to Leagues table
-- Run this if DB already initialized (postgres container already running with old schema)

ALTER TABLE "Leagues"
  ADD COLUMN IF NOT EXISTS "external_id" INT UNIQUE;

COMMENT ON COLUMN "Leagues"."external_id" IS 'SofaScore unique tournament ID (external reference)';

