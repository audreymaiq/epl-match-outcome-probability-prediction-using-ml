"""Checksum-verified, transactional PostgreSQL migrations under an advisory lock."""

from hashlib import sha256
from pathlib import Path
from sqlalchemy import text
from utils.db_connector import DatabaseConnector

ROOT = Path(__file__).resolve().parents[1] / "docker" / "postgres"
MIGRATION_LOCK = 192813001


def migrate() -> list[str]:
    applied = []
    with DatabaseConnector.get_engine().connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK})
        connection.commit()
        try:
            with connection.begin():
                connection.exec_driver_sql('''CREATE TABLE IF NOT EXISTS "SchemaMigrations" (
                    version TEXT PRIMARY KEY, checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )''')
            known = dict(connection.execute(text('SELECT version, checksum FROM "SchemaMigrations"')).all())
            has_schema = connection.execute(text("SELECT to_regclass('public.\"Matches\"') IS NOT NULL")).scalar_one()
            connection.commit()
            bootstrap = [ROOT / "init-db.sql", *[ROOT / "migrations" / name for name in (
                "001_add_leagues_external_id.sql", "002_add_elo_ratings.sql",
                "003_add_match_id_to_squad_availability.sql", "005_reconcile_feature_tables.sql",
                "006_reconcile_match_loader.sql",
            )]]
            for path in [*bootstrap, *sorted((ROOT / "migrations").glob("*.sql"))]:
                if path.name in known and known[path.name] != sha256(path.read_text(encoding="utf-8").encode()).hexdigest():
                    raise RuntimeError(f"Applied migration was modified: {path.name}")
            if not has_schema:
                if known:
                    raise RuntimeError("Migration history exists but application tables are missing")
                with connection.begin():
                    for path in bootstrap:
                        content = path.read_text(encoding="utf-8")
                        connection.exec_driver_sql(content, execution_options={"no_parameters": True})
                        connection.execute(text('INSERT INTO "SchemaMigrations" (version, checksum) VALUES (:v, :c)'),
                            {"v": path.name, "c": sha256(content.encode()).hexdigest()})
                        applied.append(path.name)
            elif not known:
                required = {
                    "Predictions": {"match_id", "model_version", "home_win_prob"},
                    "TeamFormStats": {"match_id", "team_id", "form5_matches_played"},
                    "TeamSeasonLocationStats": {"match_id", "team_id", "location", "matches_played"},
                    "HeadToHeadStats": {"match_id", "home_team_id", "away_team_id"},
                    "RefereeStats": {"match_id", "referee_id"},
                    "EloRatings": {"team_id", "match_date", "elo_before", "elo_after"},
                }
                rows = connection.execute(text('''SELECT table_name, column_name FROM information_schema.columns
                    WHERE table_schema='public' ''')).all()
                existing = {}
                for table, column in rows:
                    existing.setdefault(table, set()).add(column)
                connection.commit()
                if any(not columns <= existing.get(table, set()) for table, columns in required.items()):
                    raise RuntimeError("Legacy schema requires backup and an explicit upgrade to migration 005; automatic upgrade refused")
                with connection.begin():
                    for path in bootstrap[:-1]:
                        checksum = sha256(path.read_text(encoding="utf-8").encode()).hexdigest()
                        connection.execute(text('INSERT INTO "SchemaMigrations" (version, checksum) VALUES (:v, :c)'), {"v": path.name, "c": checksum})
            known = dict(connection.execute(text('SELECT version, checksum FROM "SchemaMigrations"')).all())
            connection.commit()
            for path in sorted((ROOT / "migrations").glob("*.sql")):
                if int(path.name[:3]) < 6:
                    continue
                content = path.read_text(encoding="utf-8")
                checksum = sha256(content.encode()).hexdigest()
                if path.name in known:
                    if known[path.name] != checksum:
                        raise RuntimeError(f"Applied migration was modified: {path.name}")
                    continue
                with connection.begin():
                    connection.exec_driver_sql(content, execution_options={"no_parameters": True})
                    connection.execute(text('INSERT INTO "SchemaMigrations" (version, checksum) VALUES (:v, :c)'), {"v": path.name, "c": checksum})
                applied.append(path.name)
        finally:
            if connection.in_transaction():
                connection.rollback()
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK})
            connection.commit()
    return applied
