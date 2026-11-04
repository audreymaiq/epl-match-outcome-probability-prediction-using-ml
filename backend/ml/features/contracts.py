"""Provenance and freshness checks for materialized feature dependencies."""

import hashlib
import json
import ast
from functools import lru_cache
from pathlib import Path
from sqlalchemy import text


FEATURE_SCHEMA_VERSION = 2


@lru_cache(maxsize=1)
def implementation_fingerprint():
    root = Path(__file__).resolve().parents[1]
    paths = sorted([*(root / "features").rglob("*.py"), *(root / "elo").rglob("*.py")])
    source = {path.relative_to(root).as_posix(): ast.dump(ast.parse(path.read_text(encoding="utf-8")),
              include_attributes=False) for path in paths}
    return hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()


def feature_fingerprint(config, competition):
    return hashlib.sha256(json.dumps({"schema_version": FEATURE_SCHEMA_VERSION,
        "implementation": implementation_fingerprint(), "history_policy": "prior_local_calendar_day", "elo": config.elo,
        "features": config.as_dict()["features"], "competition": competition.feature_rules}, sort_keys=True).encode()).hexdigest()


def source_revision(session, league_id):
    row = session.execute(text('''SELECT COUNT(*) AS count, MAX(m.updated_at) AS updated_at
        FROM "Matches" m JOIN "Seasons" s ON s.id=m.season_id
        WHERE s.league_id=:league_id AND m.status='FINISHED' '''), {"league_id": league_id}).one()
    return int(row._mapping["count"]), row.updated_at


def require_features(session, league_id, fingerprint):
    row = session.execute(text('SELECT * FROM "FeatureBuilds" WHERE league_id=:id'), {"id": league_id}).first()
    count, updated_at = source_revision(session, league_id)
    if row is None or row.config_hash != fingerprint or (row.source_match_count, row.source_updated_at) != (count, updated_at):
        raise ValueError("Materialized features are missing, stale or use a different configuration; run football features for this league/config")


def record_features(session, league_id, fingerprint, revision):
    count, updated_at = revision
    session.execute(text('''INSERT INTO "FeatureBuilds" (league_id, config_hash, source_updated_at, source_match_count)
        VALUES (:id, :hash, :updated_at, :count) ON CONFLICT (league_id) DO UPDATE SET
        config_hash=EXCLUDED.config_hash, source_updated_at=EXCLUDED.source_updated_at,
        source_match_count=EXCLUDED.source_match_count, built_at=now()'''),
        {"id": league_id, "hash": fingerprint, "updated_at": updated_at, "count": count})
