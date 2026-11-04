"""Framework independent inference against a validated training artifact."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from ml.config import parse_ml_config


DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "ensemble_model.pkl"


class ModelPredictor:
    def __init__(self, model_path: str | Path | None = None):
        self.path = Path(model_path or os.getenv("MODEL_PATH") or DEFAULT_MODEL_PATH)
        self.model: Any = None
        self.metadata: dict[str, Any] = {}
        self.feature_names: list[str] = []

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    @property
    def version(self) -> str:
        return str(self.metadata.get("version", "unknown"))

    def load(self) -> bool:
        """Return False when no artifact exists; reject malformed artifacts."""
        if self.is_loaded:
            return True
        if not self.path.is_file():
            return False
        artifact = joblib.load(self.path)
        if not isinstance(artifact, dict):
            raise ValueError("Model artifact must be a mapping")
        if artifact.get("schema_version") != 2 or artifact.get("class_order") != ["H", "D", "A"]:
            raise ValueError("Unsupported model artifact schema or class order; retrain with the current feature schema")
        model = artifact.get("model")
        names = artifact.get("feature_names")
        metadata = artifact.get("metadata")
        if not callable(getattr(model, "predict_proba", None)):
            raise ValueError("Model artifact has no probability predictor")
        if not isinstance(names, list) or not names or not all(isinstance(name, str) for name in names) or len(set(names)) != len(names):
            raise ValueError("Model artifact has invalid feature names")
        if not isinstance(metadata, dict) or not isinstance(metadata.get("version"), str) or not metadata["version"]:
            raise ValueError("Model artifact has no version")
        if "training_config" not in metadata:
            raise ValueError("Model artifact has no feature configuration")
        parse_ml_config(metadata["training_config"])
        import platform
        if "python" in metadata and metadata["python"].split(".")[:2] != platform.python_version().split(".")[:2]:
            raise ValueError("Artifact requires the same Python major and minor version as training")
        from importlib.metadata import version
        for package, expected in metadata.get("libraries", {}).items():
            if version(package) != expected:
                raise ValueError(f"Artifact requires {package}=={expected}; install matching model runtime dependencies")
        if artifact["schema_version"] == 2:
            from config.competitions import Competition
            from ml.features.contracts import feature_fingerprint
            profile = Competition(**metadata["competition"])
            if metadata.get("league") != profile.slug or metadata.get("feature_config_hash") != feature_fingerprint(parse_ml_config(metadata["training_config"]), profile):
                raise ValueError("Artifact competition or feature configuration mismatch")
        self.model = model
        self.feature_names = names
        self.metadata = metadata
        return True

    def predict(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Validate feature schema and return ordered feature row and H/D/A probabilities."""
        if not self.is_loaded:
            raise RuntimeError("No model loaded")
        if len(frame) != 1:
            raise ValueError("Inference requires exactly one fixture")
        values, probabilities = self.predict_batch(frame)
        return values, probabilities[0]

    def predict_batch(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        if not self.is_loaded:
            raise RuntimeError("No model loaded")
        if frame.empty:
            raise ValueError("Inference requires at least one row")
        missing = [name for name in self.feature_names if name not in frame]
        if missing:
            raise ValueError(f"Model features unavailable: {', '.join(missing)}")
        values = frame[self.feature_names].to_numpy(dtype=np.float32)
        if not np.isfinite(values).all():
            raise ValueError("Model features contain nonfinite values")
        probabilities = np.asarray(self.model.predict_proba(values), dtype=float)
        if probabilities.ndim == 1:
            probabilities = probabilities.reshape(1, -1)
        if probabilities.shape != (len(frame), 3) or not np.isfinite(probabilities).all():
            raise ValueError("Model returned invalid probability shape or nonfinite values")
        if np.any(probabilities < 0) or not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-4):
            raise ValueError("Model returned probabilities outside the three class simplex")
        return values, probabilities
