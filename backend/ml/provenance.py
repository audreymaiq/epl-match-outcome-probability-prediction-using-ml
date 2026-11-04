"""Capture the source that produced an artifact, including an uncommitted tree."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORIES = ("api", "config", "elt_pipeline", "ml", "operations", "providers", "utils", "docker/postgres")


def capture_source():
    paths = {ROOT / "football.py", *ROOT.glob("requirements*.txt"), ROOT / "constraints-ml.txt"}
    for directory in SOURCE_DIRECTORIES:
        paths.update(path for path in (ROOT / directory).rglob("*")
                     if path.is_file() and path.suffix in {".py", ".json", ".sql"})
    files = {path.relative_to(ROOT).as_posix(): path.read_bytes() for path in sorted(paths)}
    checksums = {name: hashlib.sha256(body).hexdigest() for name, body in files.items()}
    fingerprint = hashlib.sha256(json.dumps(checksums, sort_keys=True).encode()).hexdigest()
    return files, {"sha256": fingerprint, "files": checksums}
