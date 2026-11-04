"""Skip unchanged settled fixtures; explicit full refresh detects older detail corrections."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from config.core_constants import MatchStatus
from utils.db_connector import DatabaseConnector


def summary_fingerprint(summary):
    return hashlib.sha256(json.dumps(summary.raw, sort_keys=True, default=str).encode()).hexdigest()


def settled_matches(source, competition):
    with DatabaseConnector.session_scope() as session:
        rows = session.execute(text('''SELECT e.external_id, sm.summary_hash FROM "SourceMatchState" sm
            JOIN "Matches" m ON m.id=sm.match_id JOIN "Seasons" s ON s.id=m.season_id
            JOIN "Leagues" l ON l.id=s.league_id JOIN "ExternalMapping" e ON e.internal_id=m.id
              AND e.entity_type='match' AND e.source_system=sm.source_system AND e.scope=''
            WHERE l.slug=:league AND sm.source_system=:source AND m.status='FINISHED' '''),
            {"league": competition.slug, "source": source}).all()
    return dict(rows)


def can_skip(summary, known, refresh_days):
    if summary.start_timestamp is None:
        return False
    boundary = datetime.now(timezone.utc)-timedelta(days=refresh_days)
    return (datetime.fromtimestamp(summary.start_timestamp, timezone.utc) < boundary
        and known.get(str(summary.external_id)) == summary_fingerprint(summary))
