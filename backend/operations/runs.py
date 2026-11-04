"""Durable run records and one active mutating CLI operation per competition."""

import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import text
from utils.db_connector import DatabaseConnector


class Run:
    def __init__(self, league, command, configuration):
        self.id = str(uuid4())
        self.league, self.command, self.configuration = league, command, configuration
        self.steps = {}

    def update(self, *, status="RUNNING", error=None):
        with DatabaseConnector.get_engine().begin() as connection:
            connection.execute(text('''UPDATE "PipelineRuns" SET status=:status, steps=CAST(:steps AS jsonb),
                error=:error, finished_at=:finished WHERE run_id=:id'''),
                {"status": status, "steps": json.dumps(self.steps, default=str), "error": error,
                 "finished": None if status == "RUNNING" else datetime.now(timezone.utc), "id": self.id})

    @contextmanager
    def step(self, name):
        started = datetime.now(timezone.utc)
        self.steps[name] = {"status": "RUNNING", "started_at": started.isoformat()}
        self.update()
        result = {}
        try:
            yield result
        except BaseException as exc:
            self.steps[name].update(status="FAILED", error=type(exc).__name__, result=result)
            raise
        else:
            self.steps[name].update(status="SUCCEEDED", result=result)
        finally:
            self.steps[name]["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.update()


@contextmanager
def run_operation(league, command, configuration):
    key = int.from_bytes(hashlib.blake2b(f"football:{league}".encode(), digest_size=8).digest(), "big", signed=True)
    with DatabaseConnector.get_engine().connect() as lock:
        acquired = lock.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}).scalar_one()
        lock.commit()
        if not acquired:
            raise RuntimeError(f"Another operation is running for {league}; inspect football pipeline status")
        run = Run(league, command, configuration)
        try:
            with DatabaseConnector.get_engine().begin() as connection:
                # A released lock proves any older RUNNING record for this scope is orphaned.
                connection.execute(text('''UPDATE "PipelineRuns" SET status='INTERRUPTED', finished_at=now(),
                    error='Process ended without finalizing run' WHERE league_slug=:league AND status='RUNNING' '''), {"league": league})
                connection.execute(text('''INSERT INTO "PipelineRuns" (run_id, league_slug, command, status, configuration)
                    VALUES (:id, :league, :command, 'RUNNING', CAST(:config AS jsonb))'''),
                    {"id": run.id, "league": league, "command": command, "config": json.dumps(configuration, default=str)})
            try:
                yield run
            except BaseException as exc:
                run.update(status="INTERRUPTED" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "FAILED", error=type(exc).__name__)
                raise
            else:
                run.update(status="SUCCEEDED")
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            lock.commit()
