"""Materialize a verified feature matrix and its manifest before training."""

import hashlib
import io
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text
from config.competitions import get_competition
from ml.config import load_ml_config
from ml.features.contracts import require_features, source_revision
from ml.features.feature_extractor import FeatureExtractor
from utils.db_connector import DatabaseConnector

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data" / "datasets"


def dataset_root():
    return Path(os.getenv("DATASET_ROOT", str(DEFAULT_ROOT)))


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_]{1,100}", value):
        raise ValueError("Invalid dataset/model identifier")
    return value


def create_dataset(*, league=None, seasons=None, config_path=None):
    competition = get_competition(league)
    config = load_ml_config(config_path)
    with DatabaseConnector.session_scope() as session:
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        extractor = FeatureExtractor(session, config, competition=competition)
        require_features(session, extractor.league_id, extractor.feature_hash)
        frame = extractor.extract_all_finished_matches()
        if seasons:
            requested = {competition.season(value)[0] for value in seasons}
            missing = requested - set(frame.get("season_name", []))
            if missing:
                raise ValueError(f"No finished training matches for seasons: {sorted(missing)}")
            frame = frame[frame["season_name"].isin(requested)].copy()
        revision = source_revision(session, extractor.league_id)
    if frame.empty or not frame["outcome"].isin(["H", "D", "A"]).all():
        raise ValueError("Dataset must contain finished matches with valid H/D/A outcomes")
    if frame["match_id"].duplicated().any():
        raise ValueError("Duplicate matches in training dataset")
    frame = frame.sort_values(["match_datetime", "match_id"]).reset_index(drop=True)
    feature_names = [name for name in frame.select_dtypes(include="number").columns if name != "match_id"]
    if not feature_names or not np.isfinite(frame[feature_names].to_numpy(dtype=float)).all():
        raise ValueError("Feature dataset contains missing or nonfinite model inputs")
    body = frame.to_json(orient="table", date_format="iso", double_precision=15).encode()
    checksum = hashlib.sha256(body).hexdigest()
    identifier = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_{checksum[:16]}"
    directory = dataset_root() / competition.slug
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / safe_id(identifier)
    manifest = {
        "schema_version": 1, "dataset_id": identifier, "league": competition.slug,
        "competition": competition.as_dict(), "feature_config_hash": extractor.feature_hash,
        "training_config": config.as_dict(), "data_sha256": checksum,
        "rows": len(frame), "feature_names": feature_names,
        "seasons": sorted(frame["season_name"].unique().tolist()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": {"count": revision[0], "updated_at": str(revision[1])},
        "data_time_policy": "event_time_retrospective",
        "time_policy_note": "Historical provider corrections are not a reconstruction of information originally published before each kickoff.",
    }
    with tempfile.TemporaryDirectory(dir=directory, prefix=".snapshot_") as temporary:
        path = Path(temporary)
        (path / "data.json").write_bytes(body)
        (path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        if destination.exists():
            raise FileExistsError("Dataset identifier collision; retry snapshot creation")
        os.replace(path, destination)
    return manifest


def read_dataset(league, identifier):
    path = dataset_root() / safe_id(league) / safe_id(identifier)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    body = (path / "data.json").read_bytes()
    if manifest.get("schema_version") != 1 or manifest.get("league") != league or manifest.get("dataset_id") != identifier:
        raise ValueError("Dataset manifest identity does not match the requested dataset")
    if hashlib.sha256(body).hexdigest() != manifest["data_sha256"]:
        raise ValueError("Dataset checksum mismatch")
    frame = pd.read_json(io.StringIO(body.decode()), orient="table")
    if len(frame) != manifest["rows"] or not set(manifest["feature_names"]) <= set(frame.columns):
        raise ValueError("Dataset schema or row count mismatch")
    return frame, manifest
