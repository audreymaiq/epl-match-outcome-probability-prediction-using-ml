"""Exercise migrations, scoped features and model artifacts on disposable PostgreSQL databases."""

import json
import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def postgres_scope(monkeypatch, tmp_path):
    import sqlalchemy
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from utils.db_connector import DatabaseConnector
    from operations.migrations import migrate
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a PostgreSQL test instance with CREATE DATABASE privileges")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql":
        pytest.fail("PostgreSQL integration tests require PostgreSQL")
    name = "epl_test_" + uuid4().hex
    admin = sqlalchemy.create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
    DatabaseConnector.close_all_connections()
    monkeypatch.setenv("DATABASE_URL", parsed.set(database=name).render_as_string(hide_password=False))
    monkeypatch.setenv("DATASET_ROOT", str(tmp_path / "datasets"))
    monkeypatch.setenv("MODEL_ROOT", str(tmp_path / "models"))
    monkeypatch.delenv("MODEL_PATH", raising=False)
    try:
        migrate()
        yield DatabaseConnector
    finally:
        DatabaseConnector.close_all_connections()
        with admin.connect() as connection:
            # Only the UUID-named database created by this fixture is removed.
            connection.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


def bundle_for(profile, index=0, year=2022, *, source_league_id=None):
    from config.core_constants import MatchStatus, MatchOutcome
    from elt_pipeline.transform.data_structures import ParsedLeague, ParsedSeason, ParsedTeam, ParsedMatch, ParsedMatchBundle
    home_goals, away_goals = ((2, 0), (1, 1), (0, 2))[index % 3]
    name, start, end = profile.season(str(year))
    league_id = source_league_id or profile.providers["sofascore"]
    season = ParsedSeason(year, name, start, end, ParsedLeague(league_id, profile.name, profile.country))
    kickoff = datetime(year, 8, 1, 15, tzinfo=timezone.utc)+timedelta(days=index*3)
    match = ParsedMatch(100000+year*1000+index+league_id*10000000, season, kickoff,
        str(index//2+1), ParsedTeam(10, "Same home name"), ParsedTeam(20, "Same away name"),
        None, None, MatchStatus.FINISHED, (MatchOutcome.H, MatchOutcome.D, MatchOutcome.A)[index % 3],
        home_goals, away_goals, None, None)
    return ParsedMatchBundle(match)


def load_history(connector, profile, seasons=4, matches=45):
    from elt_pipeline.load.match_loader import MatchLoader
    with connector.session_scope() as session:
        loader = MatchLoader(session, "sofascore", competition=profile)
        for year in range(2020, 2020+seasons):
            for index in range(matches):
                loader.load_bundle(bundle_for(profile, index, year))


def quick_config(tmp_path):
    from ml.config import load_ml_config
    config = load_ml_config().as_dict()
    config["cv"].update(min_train_matches=60, min_test_matches=20)
    config["stacking"].update(min_base_matches=45, min_calibration_matches=12,
        max_oof_folds=2, min_matches_per_oof_fold=10, meta_max_iter=100)
    config["estimators"]["lightgbm"].update(n_estimators=8, n_jobs=1, verbosity=-1)
    config["estimators"]["xgboost"].update(n_estimators=8, n_jobs=1)
    config["estimators"]["catboost"].update(iterations=8, thread_count=1, allow_writing_files=False)
    path = tmp_path / "quick.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_migration_history_is_idempotent_and_preserves_data(postgres_scope):
    from operations.migrations import migrate
    from sqlalchemy import text
    from config.competitions import get_competition
    load_history(postgres_scope, get_competition(), seasons=1, matches=2)
    assert migrate() == []
    with postgres_scope.session_scope() as session:
        assert session.execute(text('SELECT COUNT(*) FROM "Matches"')).scalar_one() == 2
        assert session.execute(text('SELECT COUNT(*) FROM "SchemaMigrations"')).scalar_one() == 8


def test_season_ids_names_and_elo_are_scoped_by_competition(postgres_scope):
    from config.competitions import get_competition
    from elt_pipeline.load.match_loader import MatchLoader
    from ml.elo.elo_builder import EloBuilder
    from sqlalchemy import text
    profile = get_competition()
    other = replace(profile, slug="other_league", name="Another League", providers={"sofascore": 99})
    with postgres_scope.session_scope() as session:
        MatchLoader(session, "sofascore", profile).load_bundle(bundle_for(profile))
        MatchLoader(session, "sofascore", other).load_bundle(bundle_for(other))
        assert session.execute(text('SELECT COUNT(*) FROM "Seasons"')).scalar_one() == 2
        # A provider may reuse a season ID across tournaments.
        assert session.execute(text("SELECT COUNT(*) FROM \"ExternalMapping\" WHERE entity_type='season'")).scalar_one() == 2
        first = EloBuilder(session, competition=profile)
        first.build_from_db()
        first.save_to_db()
        second = EloBuilder(session, competition=other)
        second.build_from_db()
        second.save_to_db()
        assert session.execute(text('SELECT COUNT(*) FROM "EloRatings"')).scalar_one() == 4
        first.build_from_db()
        first.save_to_db()
        assert session.execute(text('SELECT COUNT(*) FROM "EloRatings"')).scalar_one() == 4


def test_complete_empty_snapshot_removes_children_but_unavailable_preserves_them(postgres_scope):
    from config.competitions import get_competition
    from config.core_constants import MatchEventType, MatchPeriod
    from providers.base.components import ComponentStatus
    from elt_pipeline.load.match_loader import MatchLoader
    from elt_pipeline.transform.data_structures import ParsedMatchEvent
    from sqlalchemy import text
    profile = get_competition()
    bundle = bundle_for(profile)
    bundle.events = [ParsedMatchEvent(10, MatchEventType.GOAL, bundle.match.home_team, None, None, MatchPeriod.FIRST_HALF)]
    bundle.component_status = {"events": ComponentStatus.COMPLETE}
    with postgres_scope.session_scope() as session:
        loader = MatchLoader(session, "sofascore", profile)
        match_id = loader.load_bundle(bundle)
        empty = replace(bundle, events=[], component_status={"events": ComponentStatus.UNAVAILABLE})
        loader.load_bundle(empty)
        assert session.execute(text('SELECT COUNT(*) FROM "MatchEvents" WHERE match_id=:id'), {"id": match_id}).scalar_one() == 1
        loader.load_bundle(replace(empty, component_status={"events": ComponentStatus.COMPLETE}))
        assert session.execute(text('SELECT COUNT(*) FROM "MatchEvents" WHERE match_id=:id'), {"id": match_id}).scalar_one() == 0


def test_run_lock_and_failed_step_are_persisted(postgres_scope):
    from operations.runs import run_operation
    from sqlalchemy import text
    with pytest.raises(ValueError, match="deliberate"):
        with run_operation("epl", "test", {}) as run:
            with pytest.raises(RuntimeError, match="Another operation"):
                with run_operation("epl", "test", {}):
                    pytest.fail("A concurrent writer acquired the same scope")
            with run.step("quality") as result:
                result.update(passed=False, errors=[{"reason": "deliberate quality failure"}])
                raise ValueError("deliberate quality failure")
    with postgres_scope.session_scope() as session:
        row = session.execute(text('SELECT status, steps FROM "PipelineRuns" WHERE run_id=:id'), {"id": run.id}).one()
        assert row.status == "FAILED"
        assert row.steps["quality"]["status"] == "FAILED"
        assert row.steps["quality"]["result"]["errors"] == [{"reason": "deliberate quality failure"}]


def test_real_features_snapshot_training_and_inference(postgres_scope, tmp_path):
    from config.competitions import get_competition
    from ml.features.batch.orchestrator import run_feature_pipeline
    from ml.data.snapshots import create_dataset, read_dataset
    from ml.training.train import train
    from ml.inference.predictor import ModelPredictor
    from ml.evaluation.evaluate import evaluate
    from ml.registry import release_check
    profile = get_competition()
    load_history(postgres_scope, profile)
    config = quick_config(tmp_path)
    assert run_feature_pipeline(league="epl", config_path=config)["success"]
    snapshot = create_dataset(league="epl", config_path=config)
    frame, manifest = read_dataset("epl", snapshot["dataset_id"])
    assert len(frame) == 180
    assert {"match_datetime", "season_name"} <= set(frame)
    assert "match_id" not in manifest["feature_names"]
    assert frame["home_availability_known"].eq(0).all()
    candidate = train(league="epl", config_path=config, dataset_id=snapshot["dataset_id"])
    assert Path(candidate["model_path"]).is_file()
    predictor = ModelPredictor(candidate["model_path"])
    assert predictor.load()
    _, probabilities = predictor.predict(frame.iloc[[0]])
    assert probabilities.sum() == pytest.approx(1)
    assert isinstance(release_check("epl", candidate["model_version"])["passed"], bool)
    with pytest.raises(ValueError, match="overlaps"):
        evaluate("epl", candidate["model_version"], snapshot["dataset_id"])
    # Corrupt feature data must not be silently accepted.
    path = Path(os.environ["DATASET_ROOT"])/"epl"/snapshot["dataset_id"]/"data.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        read_dataset("epl", snapshot["dataset_id"])


def test_active_model_changes_are_visible_without_api_restart(postgres_scope):
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from config.competitions import get_competition
    from config.core_constants import MatchStatus
    from elt_pipeline.load.match_loader import MatchLoader
    from ml.config import load_ml_config
    from ml.features.contracts import feature_fingerprint
    from ml.features.batch.orchestrator import run_feature_pipeline
    from ml.models.baselines import FrequencyClassifier
    from ml.registry import save_candidate, promote, rollback
    from api.services.prediction_service import PredictionService
    from api.dependencies import get_prediction_service
    from api.main import create_app
    profile, config = get_competition(), load_ml_config()
    load_history(postgres_scope, profile, seasons=1, matches=3)
    run_feature_pipeline()
    fixture = bundle_for(profile, index=1, year=2031)
    fixture.match = replace(fixture.match, status=MatchStatus.SCHEDULED, outcome=None, home_goals=None, away_goals=None)
    with postgres_scope.session_scope() as session:
        match_id = MatchLoader(session, "sofascore", profile).load_bundle(fixture)
    import numpy as np
    model = FrequencyClassifier().fit(np.zeros((3, 1)), np.array([0, 1, 2]))
    # These declared scores are test fixtures for the release protocol, not a claim of trained performance.
    metadata = {"league": "epl", "competition": profile.as_dict(), "training_config": config.as_dict(),
        "feature_config_hash": feature_fingerprint(config, profile),
        "cv_metrics": {"n_folds": 2, "mean_log_loss": 0.8},
        "frequency_cv_metrics": {"mean_log_loss": 1.1}, "walk_forward_folds": 2}
    for version in ("fixture_v1", "fixture_v2"):
        save_candidate({"schema_version": 2, "class_order": ["H", "D", "A"], "model": model,
            "feature_names": ["match_week"], "metadata": {**metadata, "version": version}})
    promote("epl", "fixture_v1")
    service = PredictionService()
    app = create_app()
    app.dependency_overrides[get_prediction_service] = lambda: service
    client = TestClient(app)
    assert client.get("/api/v1/model/info").json()["version"] == "fixture_v1"
    assert client.get("/ready").status_code == 200
    assert client.get("/health").json()["model_loaded"] is True
    assert client.get(f"/api/v1/predictions/model-probabilities/{match_id}").status_code == 200
    with postgres_scope.session_scope() as session:
        assert session.execute(text('SELECT COUNT(*) FROM "Predictions"')).scalar_one() == 0
    for _ in range(2):
        response = client.post("/api/v1/predictions", json={"match_id": match_id})
        assert response.status_code == 200, response.text
    assert client.get("/api/v1/predictions").status_code == 200
    from monitoring.collector import PipelineCollector
    metrics = list(PipelineCollector().collect())
    assert next(metric for metric in metrics if metric.name == "football_monitoring_available").samples[0].value == 1
    with postgres_scope.session_scope() as session:
        assert session.execute(text('SELECT COUNT(*) FROM "Predictions"')).scalar_one() == 1
    promote("epl", "fixture_v2")
    assert client.get("/api/v1/model/info").json()["version"] == "fixture_v2"
    rollback("epl")
    assert client.get("/api/v1/model/info").json()["version"] == "fixture_v1"
    with postgres_scope.session_scope() as session:
        session.execute(text('DELETE FROM "FeatureBuilds"'))
    assert client.get("/ready").status_code == 503


def test_existing_legacy_data_survives_adoption_of_migration_history(postgres_scope):
    from sqlalchemy import text
    from operations.migrations import ROOT, migrate
    with postgres_scope.get_engine().begin() as connection:
        connection.exec_driver_sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public')
        for path in [ROOT/"init-db.sql", *[ROOT/"migrations"/name for name in (
            "001_add_leagues_external_id.sql", "002_add_elo_ratings.sql",
            "003_add_match_id_to_squad_availability.sql", "005_reconcile_feature_tables.sql",
            "006_reconcile_match_loader.sql")]]:
            connection.exec_driver_sql(path.read_text(encoding="utf-8"), execution_options={"no_parameters": True})
        connection.exec_driver_sql('''INSERT INTO "Leagues" (name, country, external_id) VALUES ('Premier League','England',17);
            INSERT INTO "Teams" (name) VALUES ('Legacy home'), ('Legacy away');
            INSERT INTO "Seasons" (league_id, name, start_year, end_year) VALUES (1,'2024/2025',2024,2025);
            INSERT INTO "Matches" (season_id, home_team_id, away_team_id, match_datetime, status, outcome, home_goals, away_goals)
            VALUES (1,1,2,'2024-08-01 15:00:00','FINISHED','H',1,0)''')
    applied = migrate()
    assert "005_reconcile_feature_tables.sql" not in applied
    with postgres_scope.session_scope() as session:
        assert session.execute(text('SELECT COUNT(*) FROM "Matches"')).scalar_one() == 1
        assert session.execute(text('SELECT slug FROM "Leagues" WHERE id=1')).scalar_one() == "epl"


def test_team_endpoints_reject_entities_outside_selected_competition(postgres_scope):
    from config.competitions import get_competition
    from api.services.team_service import TeamService
    from api.exceptions import NotFoundException
    from sqlalchemy import text
    profile = get_competition()
    load_history(postgres_scope, profile, seasons=1, matches=1)
    with postgres_scope.session_scope() as session:
        outsider = session.execute(text('INSERT INTO "Teams" (name) VALUES (\'Outside league\') RETURNING id')).scalar_one()
        service = TeamService(session, profile)
        for lookup in (service.get_team_detail, service.get_team_form, service.get_team_stats):
            with pytest.raises(NotFoundException):
                lookup(outsider)
        with pytest.raises(NotFoundException):
            service.get_h2h(outsider, 1)


def test_populated_read_endpoints_work_without_a_model(postgres_scope):
    from fastapi.testclient import TestClient
    from config.competitions import get_competition
    from api.main import create_app
    from api.dependencies import get_prediction_service
    from api.services.prediction_service import PredictionService
    load_history(postgres_scope, get_competition(), seasons=1, matches=3)
    app = create_app()
    app.dependency_overrides[get_prediction_service] = lambda: PredictionService()
    client = TestClient(app)
    for path in ("/live", "/health", "/api/v1/leagues", "/api/v1/matches", "/api/v1/matches/seasons",
                 "/api/v1/matches/1", "/api/v1/teams", "/api/v1/teams/1", "/api/v1/teams/1/form",
                 "/api/v1/teams/1/stats", "/api/v1/teams/head-to-head?home_team_id=1&away_team_id=2",
                 "/api/v1/model/info", "/api/v1/model/performance", "/api/v1/predictions"):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
    assert client.get("/ready").status_code == 503
    assert client.get("/api/v1/teams?league=not_configured").status_code == 422


def test_features_exclude_results_from_the_target_local_matchday(postgres_scope):
    from config.competitions import get_competition
    from elt_pipeline.load.match_loader import MatchLoader
    from ml.features.batch.orchestrator import run_feature_pipeline
    from ml.features.feature_extractor import FeatureExtractor
    profile = get_competition()
    first = bundle_for(profile)
    second = bundle_for(profile, index=1)
    second.match = replace(second.match, match_datetime=first.match.match_datetime+timedelta(hours=4))
    with postgres_scope.session_scope() as session:
        loader = MatchLoader(session, "sofascore", profile)
        loader.load_bundle(first)
        identifier = loader.load_bundle(second)
    run_feature_pipeline()
    with postgres_scope.session_scope() as session:
        features = FeatureExtractor(session).extract_for_match(identifier).iloc[0]
        assert features["home_form5_matches_played"] == 0


def test_head_to_head_combines_both_venues_for_the_selected_teams(postgres_scope):
    from config.competitions import get_competition
    from api.services.team_service import TeamService
    from elt_pipeline.load.match_loader import MatchLoader
    profile = get_competition()
    first = bundle_for(profile)
    second = bundle_for(profile, index=3)
    second.match = replace(second.match, home_team=first.match.away_team, away_team=first.match.home_team)
    with postgres_scope.session_scope() as session:
        loader = MatchLoader(session, "sofascore", profile)
        loader.load_bundle(first)
        loader.load_bundle(second)
        report = TeamService(session, profile).get_h2h(1, 2)
        assert report.total_meetings == 2
        assert report.home_wins == report.away_wins == 1
        assert report.avg_home_goals == report.avg_away_goals == 1
        assert len(report.recent_matches) == 2
