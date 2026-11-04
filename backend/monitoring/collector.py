"""Collect bounded competition labels from durable operational records."""

import time
import threading
from prometheus_client.core import GaugeMetricFamily
from sqlalchemy import text
from utils.db_connector import DatabaseConnector

_registered = False
_registration_lock = threading.Lock()


def register_metrics():
    global _registered
    from prometheus_client import REGISTRY
    with _registration_lock:
        if not _registered:
            REGISTRY.register(PipelineCollector())
            _registered = True


class PipelineCollector:
    def describe(self):
        return []

    def collect(self):
        available = GaugeMetricFamily("football_monitoring_available", "Database monitoring collection succeeded")
        try:
            with DatabaseConnector.session_scope() as session:
                from config.competitions import competitions
                profiles = competitions()
                rows = session.execute(text('''SELECT league_slug,
                    MAX(finished_at) FILTER(WHERE status='SUCCEEDED' AND command IN ('ingest','pipeline')) AS last_success,
                    COUNT(*) FILTER(WHERE status='FAILED' AND started_at>now()-interval '24 hours') AS failures,
                    MIN(started_at) FILTER(WHERE status='RUNNING') AS oldest_running
                    FROM "PipelineRuns" GROUP BY league_slug''')).mappings().all()
                coverage = session.execute(text('''SELECT l.slug, MAX(o.observed_at) AS observed_at
                    FROM "IngestionObservations" o JOIN "Matches" m ON m.id=o.match_id
                    JOIN "Seasons" s ON s.id=m.season_id JOIN "Leagues" l ON l.id=s.league_id GROUP BY l.slug''')).all()
                quality = session.execute(text('''SELECT d.league_slug, COUNT(*) AS evaluated,
                    AVG(-LN(GREATEST(CASE m.outcome WHEN 'H' THEN p.home_win_prob
                        WHEN 'D' THEN p.draw_prob WHEN 'A' THEN p.away_win_prob END, 0.000001))) AS log_loss,
                    AVG(CASE WHEN p.predicted_outcome=m.outcome::text THEN 1.0 ELSE 0.0 END) AS accuracy
                    FROM "ModelDeployments" d JOIN "Predictions" p ON p.model_version=d.model_version
                    JOIN "Matches" m ON m.id=p.match_id JOIN "Seasons" s ON s.id=m.season_id
                    JOIN "Leagues" l ON l.id=s.league_id AND l.slug=d.league_slug
                    WHERE m.status='FINISHED' AND m.outcome IS NOT NULL
                    AND m.match_datetime >= (now() AT TIME ZONE 'UTC')-interval '90 days'
                    AND p.created_at < m.match_datetime GROUP BY d.league_slug''')).mappings().all()
            succeeded = GaugeMetricFamily("football_ingestion_last_success_timestamp_seconds", "Last successful ingest/pipeline", labels=["league"])
            failures = GaugeMetricFamily("football_runs_failed_24h", "Failed CLI operations in the last 24 hours", labels=["league"])
            running = GaugeMetricFamily("football_run_duration_seconds", "Age of oldest running operation", labels=["league"])
            observed = GaugeMetricFamily("football_data_last_observation_timestamp_seconds", "Latest recorded source observation", labels=["league"])
            sample_count = GaugeMetricFamily("football_model_evaluated_90d", "Scored pre-match predictions for the active model in 90 days", labels=["league"])
            log_loss = GaugeMetricFamily("football_model_log_loss_90d", "Active model observed log loss in 90 days", labels=["league"])
            accuracy = GaugeMetricFamily("football_model_accuracy_90d", "Active model observed accuracy in 90 days", labels=["league"])
            runs_by_league = {row["league_slug"]: row for row in rows}
            coverage_by_league = dict(coverage)
            quality_by_league = {row["league_slug"]: row for row in quality}
            for slug in profiles:
                row = runs_by_league.get(slug, {})
                timestamp = row.get("last_success")
                succeeded.add_metric([slug], timestamp.timestamp() if timestamp else 0)
                failures.add_metric([slug], row.get("failures", 0))
                oldest = row.get("oldest_running")
                running.add_metric([slug], max(0, time.time()-oldest.timestamp()) if oldest else 0)
                timestamp = coverage_by_league.get(slug)
                observed.add_metric([slug], timestamp.timestamp() if timestamp else 0)
                score = quality_by_league.get(slug)
                sample_count.add_metric([slug], score["evaluated"] if score else 0)
                if score:
                    log_loss.add_metric([slug], float(score["log_loss"]))
                    accuracy.add_metric([slug], float(score["accuracy"]))
            available.add_metric([], 1)
            yield succeeded
            yield failures
            yield running
            yield observed
            yield sample_count
            yield log_loss
            yield accuracy
        except Exception:
            available.add_metric([], 0)
        yield available
