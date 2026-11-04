"""One operational CLI for ingestion, datasets, training and model releases."""

import argparse
import json
import logging
import os
import sys
import signal
import threading
from pathlib import Path


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="Apply verified migrations to a fresh or supported existing database")
    commands.add_parser("leagues", help="List configured competitions")
    for name in ("ingest", "features", "dataset", "train", "quality", "evaluate"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--league", default=None)
        if name in {"features", "dataset", "train"}:
            cmd.add_argument("--config")
        if name in {"ingest", "dataset", "train", "quality"}:
            group = cmd.add_mutually_exclusive_group()
            group.add_argument("--seasons", nargs="+")
            if name == "ingest":
                group.add_argument("--season-count", type=int)
        if name == "ingest":
            cmd.add_argument("--source", default=os.getenv("PROVIDER", "sofascore"))
            cmd.add_argument("--mode", choices=["full", "incremental"], default="incremental")
            cmd.add_argument("--refresh-days", type=int, default=7)
        if name in {"train", "evaluate"}:
            cmd.add_argument("--dataset", required=name == "evaluate")
        if name == "evaluate":
            cmd.add_argument("--model-version", required=True)
    pipeline = commands.add_parser("pipeline")
    pipeline_commands = pipeline.add_subparsers(dest="action", required=True)
    run = pipeline_commands.add_parser("run")
    run.add_argument("--league", default=None)
    run.add_argument("--source", default=os.getenv("PROVIDER", "sofascore"))
    run.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    run.add_argument("--refresh-days", type=int, default=7)
    group = run.add_mutually_exclusive_group()
    group.add_argument("--seasons", nargs="+")
    group.add_argument("--season-count", type=int)
    run.add_argument("--train-seasons", nargs="+")
    run.add_argument("--config")
    run.add_argument("--promote", action="store_true")
    run.add_argument("--no-train", action="store_true", help="Update data and features without training a candidate")
    run.add_argument("--release-policy")
    status = pipeline_commands.add_parser("status")
    status.add_argument("--run-id")
    status.add_argument("--league", default=None)
    model = commands.add_parser("model")
    model_commands = model.add_subparsers(dest="action", required=True)
    for name in ("check", "promote", "rollback", "status"):
        cmd = model_commands.add_parser(name)
        cmd.add_argument("--league", default=None)
        if name in {"check", "promote"}:
            cmd.add_argument("--model-version", required=True)
            cmd.add_argument("--release-policy")
    identity = commands.add_parser("identity")
    identity.add_argument("--league", default=None, help="Lock scope for reconciliation")
    identity.add_argument("--source", required=True)
    identity.add_argument("--entity", required=True)
    identity.add_argument("--external-id", required=True)
    identity.add_argument("--internal-id", required=True, type=int)
    identity.add_argument("--scope", default="")
    drift = commands.add_parser("drift", help="Compare immutable feature datasets; diagnostic only")
    drift.add_argument("--league", default=None)
    drift.add_argument("--reference", required=True)
    drift.add_argument("--current", required=True)
    drift.add_argument("--bins", type=int, default=10)
    drift.add_argument("--smoothing", type=float, default=1e-6)
    drift.add_argument("--threshold", type=float, default=0.2)
    return root


def execute(args):
    from config.competitions import get_competition, competitions
    if args.command == "leagues":
        return {key: value.as_dict() for key, value in competitions().items()}
    if args.command == "migrate":
        from operations.migrations import migrate
        return {"applied": migrate()}
    competition = get_competition(args.league)
    from sqlalchemy import text
    from utils.db_connector import DatabaseConnector
    if args.command == "pipeline" and args.action == "status":
        with DatabaseConnector.session_scope() as session:
            if args.run_id:
                from uuid import UUID
                identifier = str(UUID(args.run_id))
                rows = session.execute(text('SELECT * FROM "PipelineRuns" WHERE run_id=:id AND league_slug=:league'),
                    {"id": identifier, "league": competition.slug}).mappings().all()
            else:
                rows = session.execute(text('SELECT * FROM "PipelineRuns" WHERE league_slug=:league ORDER BY started_at DESC LIMIT 20'),
                    {"league": competition.slug}).mappings().all()
            return {"runs": [dict(row) for row in rows]}
    if args.command == "model" and args.action == "status":
        with DatabaseConnector.session_scope() as session:
            row = session.execute(text('SELECT * FROM "ModelDeployments" WHERE league_slug=:league'), {"league": competition.slug}).mappings().first()
            return {"deployment": dict(row) if row else None}
    configuration = {key: value for key, value in vars(args).items() if value is not None}
    configuration["competition"] = competition.as_dict()
    if hasattr(args, "config"):
        from ml.config import load_ml_config
        configuration["ml_config"] = load_ml_config(args.config).as_dict()
    from operations.runs import run_operation
    if getattr(args, "no_train", False) and getattr(args, "promote", False):
        raise ValueError("--no-train cannot be combined with --promote")
    with run_operation(competition.slug, args.command, configuration) as run:
        def step(name, function, **kwargs):
            with run.step(name) as record:
                result = function(**kwargs)
                record.update(result)
                if result.get("success") is False or result.get("passed") is False:
                    raise ValueError(f"Step {name} failed; inspect run {run.id}")
                return result
        common = {"league": competition.slug}
        if args.command == "drift":
            from ml.evaluation.drift import diagnose
            return {"run_id": run.id, **step("drift", diagnose, reference_id=args.reference,
                current_id=args.current, bins=args.bins, smoothing=args.smoothing, threshold=args.threshold, **common)}
        if args.command in {"ingest", "pipeline"}:
            from elt_pipeline.orchestrator import run_pipeline
            ingestion = step("ingest", run_pipeline, provider_name=args.source,
                specific_seasons=args.seasons, season_count=args.season_count, mode=args.mode, refresh_days=args.refresh_days, **common)
            if args.command == "ingest":
                return {"run_id": run.id, **ingestion}
        if args.command in {"quality", "pipeline"}:
            from operations.quality import check_data
            quality = step("quality", check_data, seasons=args.seasons, **common)
            if args.command == "quality":
                return {"run_id": run.id, **quality}
        if args.command in {"features", "pipeline"}:
            from ml.features.batch.orchestrator import run_feature_pipeline
            result = step("features", run_feature_pipeline, config_path=args.config, **common)
            if args.command == "features":
                return {"run_id": run.id, **result}
            if args.no_train:
                return {"run_id": run.id, **result}
        if args.command in {"dataset", "pipeline"}:
            from ml.data.snapshots import create_dataset
            result = step("dataset", create_dataset, config_path=args.config,
                seasons=args.train_seasons if args.command == "pipeline" else args.seasons, **common)
            if args.command == "dataset":
                return {"run_id": run.id, **result}
            dataset_id = result["dataset_id"]
        if args.command in {"train", "pipeline"}:
            from ml.training.train import train
            result = step("train", train, config_path=args.config,
                dataset_id=dataset_id if args.command == "pipeline" else args.dataset,
                seasons=args.seasons if args.command == "train" else None, **common)
            if args.command == "pipeline" and args.promote:
                from ml.registry import promote
                result["release"] = step("promote", promote, version=result["model_version"], policy_path=args.release_policy, **common)
            return {"run_id": run.id, **result}
        if args.command == "evaluate":
            from ml.evaluation.evaluate import evaluate
            return {"run_id": run.id, **step("evaluate", evaluate, version=args.model_version, dataset_id=args.dataset, **common)}
        if args.command == "model":
            from ml.registry import promote, release_check, rollback
            function = {"check": release_check, "promote": promote, "rollback": rollback}[args.action]
            kwargs = {} if args.action == "rollback" else {"version": args.model_version, "policy_path": args.release_policy}
            return {"run_id": run.id, **step(args.action, function, **common, **kwargs)}
        if args.command == "identity":
            from operations.identity import link_entity
            return {"run_id": run.id, **step("link", link_entity, source=args.source, entity_type=args.entity,
                external_id=args.external_id, internal_id=args.internal_id, scope=args.scope)}
        raise ValueError("Unsupported command")


def main(argv=None):
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
    args = parser().parse_args(argv)
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, interrupted)
    logging.basicConfig(stream=sys.stderr, level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        result = execute(args)
    except KeyboardInterrupt:
        print(json.dumps({"success": False, "error": "Interrupted"}), file=sys.stderr)
        return 130
    except Exception as exc:
        logging.error("Command failed: %s", exc)
        print(json.dumps({"success": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, default=str, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
