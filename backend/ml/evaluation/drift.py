"""Univariate feature distribution diagnostics against an immutable reference."""

import numpy as np
from ml.data.snapshots import read_dataset


def distribution_shift(reference, current, *, bins=10, smoothing=1e-6):
    if type(bins) is not int or not 2 <= bins <= 100:
        raise ValueError("bins must be an integer from 2 to 100")
    if not np.isfinite(smoothing) or not 0 < smoothing < 1:
        raise ValueError("smoothing must be finite and between 0 and 1")
    reference, current = np.asarray(reference, dtype=float), np.asarray(current, dtype=float)
    if reference.ndim != 1 or current.ndim != 1 or not reference.size or not current.size:
        raise ValueError("Drift diagnostics require two nonempty feature vectors")
    if not np.isfinite(reference).all() or not np.isfinite(current).all():
        raise ValueError("Drift features must be finite")
    # Midpoints create two bins for a constant reference, so previously unseen
    # values do not disappear into one infinite bucket.
    unique = np.unique(np.quantile(reference, np.linspace(0, 1, bins+1)))
    internal = unique[:-1]/2+unique[1:]/2 if len(unique) > 1 else np.array([
        np.nextafter(unique[0], -np.inf), np.nextafter(unique[0], np.inf)])
    edges = np.concatenate(([-np.inf], internal, [np.inf]))
    left = np.histogram(reference, bins=edges)[0].astype(float)+smoothing
    right = np.histogram(current, bins=edges)[0].astype(float)+smoothing
    left /= left.sum()
    right /= right.sum()
    return {"psi": float(np.sum((right-left)*np.log(right/left))),
        "reference_mean": float(reference.mean()), "current_mean": float(current.mean()),
        "reference_rows": reference.size, "current_rows": current.size}


def diagnose(league, reference_id, current_id, *, bins=10, smoothing=1e-6, threshold=0.2):
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("Drift threshold must be finite and nonnegative")
    reference, reference_manifest = read_dataset(league, reference_id)
    current, current_manifest = read_dataset(league, current_id)
    if reference_manifest["feature_config_hash"] != current_manifest["feature_config_hash"]:
        raise ValueError("Cannot compare different feature contracts")
    names = reference_manifest["feature_names"]
    if names != current_manifest["feature_names"]:
        raise ValueError("Drift feature schemas differ")
    features = {name: distribution_shift(reference[name], current[name], bins=bins, smoothing=smoothing) for name in names}
    return {"league": league, "reference_dataset": reference_id, "current_dataset": current_id,
        "bins": bins, "smoothing": smoothing, "threshold": threshold, "features": features,
        "flagged_features": [name for name, result in features.items() if result["psi"] > threshold],
        "interpretation": "Univariate diagnostics; sample size and season mix affect PSI. This does not establish predictive degradation or trigger retraining."}
