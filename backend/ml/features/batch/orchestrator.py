"""Rebuild a competition's materialized features atomically with one configuration."""

import argparse
import time
from config.competitions import get_competition, competition_id
from ml.config import load_ml_config
from ml.features.contracts import feature_fingerprint, source_revision, record_features
from ml.features.batch.computers import EloComputer, FormComputer, H2HComputer, RefereeComputer, SeasonComputer
from utils.db_connector import DatabaseConnector


def run_feature_pipeline(season_name=None, skip=None, *, league=None, config_path=None):
    if season_name or skip:
        raise ValueError("A consistent feature build requires the full competition history; partial rebuilds are not published")
    competition = get_competition(league)
    config = load_ml_config(config_path)
    started = time.monotonic()
    summary = {"success": False, "league": competition.slug, "computers": {}}
    with DatabaseConnector.session_scope() as session:
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        league_id = competition_id(session, competition)
        revision = source_revision(session, league_id)
        for table in ("TeamFormStats", "TeamSeasonLocationStats", "HeadToHeadStats", "RefereeStats"):
            from sqlalchemy import text
            session.execute(text(f'''DELETE FROM "{table}" f USING "Matches" m, "Seasons" s
                WHERE f.match_id=m.id AND s.id=m.season_id AND s.league_id=:league_id'''), {"league_id": league_id})
        for computer in (EloComputer(), FormComputer(), SeasonComputer(), H2HComputer(), RefereeComputer()):
            before = time.monotonic()
            rows = computer.compute(session, league_id=league_id, competition=competition, config=config)
            summary["computers"][computer.name] = {"rows": rows, "duration_s": time.monotonic()-before}
        fingerprint = feature_fingerprint(config, competition)
        record_features(session, league_id, fingerprint, revision)
    summary.update(success=True, config_hash=fingerprint, duration_seconds=time.monotonic()-started)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league")
    parser.add_argument("--config")
    args = parser.parse_args()
    run_feature_pipeline(league=args.league, config_path=args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
