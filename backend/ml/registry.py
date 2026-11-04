"""Immutable artifact storage and transactional activation pointers."""

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path

import joblib
from sqlalchemy import text
from ml.data.snapshots import safe_id
from utils.db_connector import DatabaseConnector

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "models"


def model_root():
    return Path(os.getenv("MODEL_ROOT", str(DEFAULT_ROOT)))


def model_path(league, version):
    return model_root() / safe_id(league) / safe_id(version) / "model.pkl"


def save_candidate(artifact, *, source_files=None):
    metadata = artifact["metadata"]
    destination = model_path(metadata["league"], metadata["version"]).parent
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".candidate_") as temporary:
        directory = Path(temporary)
        joblib.dump(artifact, directory / "model.pkl")
        checksum = hashlib.sha256((directory / "model.pkl").read_bytes()).hexdigest()
        manifest = {"schema_version": 1, "sha256": checksum, "metadata": metadata}
        if source_files:
            with zipfile.ZipFile(directory / "source.zip", "w", zipfile.ZIP_DEFLATED) as bundle:
                for name, body in source_files.items():
                    bundle.writestr(name, body)
            manifest["source_bundle_sha256"] = hashlib.sha256((directory / "source.zip").read_bytes()).hexdigest()
        (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        if destination.exists():
            raise FileExistsError("Model versions are immutable")
        os.replace(directory, destination)
    return destination / "model.pkl"


def verified_manifest(league, version):
    path = model_path(league, version)
    manifest = json.loads(path.with_name("manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["sha256"]:
        raise ValueError("Model checksum mismatch")
    if "source_bundle_sha256" in manifest and hashlib.sha256(path.with_name("source.zip").read_bytes()).hexdigest() != manifest["source_bundle_sha256"]:
        raise ValueError("Model source bundle checksum mismatch")
    if manifest["metadata"]["league"] != league or manifest["metadata"]["version"] != version:
        raise ValueError("Model identity mismatch")
    return manifest


def release_check(league, version, policy_path=None):
    import math
    metadata = verified_manifest(league, version)["metadata"]
    path = Path(policy_path or os.getenv("RELEASE_POLICY_PATH") or Path(__file__).with_name("config") / "release.json")
    policy = json.loads(path.read_text(encoding="utf-8"))
    metrics = metadata["cv_metrics"]
    loss = metrics.get("mean_log_loss")
    baseline = metadata["frequency_cv_metrics"].get("mean_log_loss")
    reasons = []
    if type(policy.get("min_folds")) is not int or policy["min_folds"] < 1:
        raise ValueError("Release policy min_folds must be a positive integer")
    for name in ("max_log_loss", "required_log_loss_improvement"):
        if type(policy.get(name)) not in (int, float) or not math.isfinite(policy[name]) or policy[name] < 0:
            raise ValueError(f"Invalid release policy {name}")
    if metrics.get("n_folds", 0) < policy["min_folds"]:
        reasons.append("Too few chronological evaluation folds")
    if not isinstance(loss, (int, float)) or not math.isfinite(loss) or loss > policy["max_log_loss"]:
        reasons.append("Log loss exceeds the configured limit")
    if (not isinstance(baseline, (int, float)) or not math.isfinite(baseline)
        or not isinstance(loss, (int, float)) or not math.isfinite(loss)
        or baseline-loss < policy["required_log_loss_improvement"]):
        reasons.append("Candidate does not improve sufficiently over the training-frequency baseline")
    return {"passed": not reasons, "reasons": reasons, "policy": policy, "model_version": version, "league": league}


def promote(league, version, *, policy_path=None):
    result = release_check(league, version, policy_path)
    if not result["passed"]:
        raise ValueError("Release gate failed: " + "; ".join(result["reasons"]))
    # Validate the actual artifact, not just its JSON metadata, before activation.
    from ml.inference.predictor import ModelPredictor
    predictor = ModelPredictor(model_path(league, version))
    predictor.load()
    with DatabaseConnector.session_scope() as session:
        session.execute(text('''INSERT INTO "ModelDeployments" (league_slug, model_version)
            VALUES (:league, :version) ON CONFLICT (league_slug) DO UPDATE SET
            previous_version="ModelDeployments".model_version, model_version=EXCLUDED.model_version,
            activated_at=now() WHERE "ModelDeployments".model_version <> EXCLUDED.model_version'''),
            {"league": league, "version": version})
    return result


def rollback(league):
    with DatabaseConnector.session_scope() as session:
        row = session.execute(text('SELECT * FROM "ModelDeployments" WHERE league_slug=:league FOR UPDATE'), {"league": league}).first()
        if row is None or not row.previous_version:
            raise ValueError("No previous model version is recorded")
        verified_manifest(league, row.previous_version)
        from ml.inference.predictor import ModelPredictor
        ModelPredictor(model_path(league, row.previous_version)).load()
        session.execute(text('''UPDATE "ModelDeployments" SET model_version=:previous,
            previous_version=:current, activated_at=now() WHERE league_slug=:league'''),
            {"previous": row.previous_version, "current": row.model_version, "league": league})
    return {"league": league, "model_version": row.previous_version}
