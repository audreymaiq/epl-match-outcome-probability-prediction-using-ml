"""Load one immutable, validated configuration for a training run."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path(__file__).with_name("default.json")


@dataclass(frozen=True)
class CVConfig:
    test_seasons: int
    min_train_seasons: int
    gap_rounds: int
    min_train_matches: int
    min_test_matches: int


@dataclass(frozen=True)
class StackingConfig:
    calibration_fraction: float
    min_calibration_matches: int
    min_base_matches: int
    max_oof_folds: int
    min_matches_per_oof_fold: int
    meta_c: float
    meta_max_iter: int


@dataclass(frozen=True)
class FeatureConfig:
    form_decay: float
    expected_home_goals_multiplier: float
    h2h_over_2_5_prior: float
    h2h_btts_prior: float
    referee_avg_reds_prior: float
    referee_cards_scale: float
    rest_days_max: float
    top_teams: list[str]
    derbies: list[list[str]]
    min_matches: dict[str, int]
    defaults: dict[str, float]


@dataclass(frozen=True)
class MLConfig:
    model_name: str
    random_seed: int
    elo: dict[str, float]
    features: FeatureConfig
    cv: CVConfig
    stacking: StackingConfig
    estimators: dict[str, dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)


def _section(data: dict[str, Any], key: str, fields: set[str]) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"ML config section '{key}' must contain exactly: {sorted(fields)}")
    return value


def _positive_int(value: Any, name: str, *, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"ML config '{name}' must be an integer >= {minimum}")
    return value


def parse_ml_config(data: dict[str, Any]) -> MLConfig:
    """Validate a configuration mapping, including one stored in an artifact."""
    if not isinstance(data, dict) or set(data) != {"model_name", "random_seed", "elo", "features", "cv", "stacking", "estimators"}:
        raise ValueError("ML config must contain model_name, random_seed, elo, features, cv, stacking, estimators")
    if not isinstance(data["model_name"], str) or not data["model_name"].isidentifier():
        raise ValueError("ML config model_name must be a safe filename stem")
    _positive_int(data["random_seed"], "random_seed", minimum=0)
    elo = _section(data, "elo", {
        "initial_elo", "home_advantage", "rating_scale", "k_base", "k_big_match", "k_early_season",
        "k_max", "season_regression_factor", "gd_weight", "gd_cap", "elo_min", "elo_max",
        "draw_base", "draw_reduction", "draw_min", "draw_slope", "draw_midpoint",
    })
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in elo.values()):
        raise ValueError("ML config elo parameters must be numeric")
    if not elo["elo_min"] < elo["initial_elo"] < elo["elo_max"]:
        raise ValueError("ML config elo bounds must contain initial_elo")
    if not 0 <= elo["season_regression_factor"] <= 1:
        raise ValueError("ML config elo season_regression_factor must be in [0, 1]")
    if min(elo[name] for name in ("rating_scale", "k_base", "k_big_match", "k_early_season", "k_max", "gd_weight", "gd_cap", "draw_slope")) <= 0:
        raise ValueError("ML config elo update weights must be positive")
    if not 0 <= elo["draw_min"] <= elo["draw_base"] <= 1 or not 0 <= elo["draw_reduction"] <= elo["draw_base"]:
        raise ValueError("ML config elo draw probability bounds are invalid")
    feature_data = _section(data, "features", set(FeatureConfig.__dataclass_fields__))
    default_keys = {
        "elo", "elo_diff", "elo_win_prob_home", "form5_ppg", "form5_avg_scored",
        "form5_avg_conceded", "season_ppg", "season_avg_scored", "season_avg_conceded",
        "h2h_home_win_rate", "h2h_draw_rate", "h2h_avg_goals", "referee_home_win_rate",
        "referee_draw_rate", "referee_avg_yellows", "rest_days", "form5_clean_sheets",
        "attack_strength", "defense_strength",
    }
    defaults = feature_data["defaults"]
    minimums = feature_data["min_matches"]
    if not isinstance(defaults, dict) or set(defaults) != default_keys or any(
        type(value) not in (int, float) or not math.isfinite(value) for value in defaults.values()
    ):
        raise ValueError("ML config features.defaults has missing or invalid values")
    if not isinstance(minimums, dict) or set(minimums) != {"form", "h2h", "referee", "season"}:
        raise ValueError("ML config features.min_matches has missing values")
    for name, value in minimums.items():
        _positive_int(value, f"features.min_matches.{name}")
    decay = feature_data["form_decay"]
    if type(decay) not in (int, float) or not math.isfinite(decay) or not 0 < decay <= 1:
        raise ValueError("ML config features.form_decay must be in (0, 1]")
    for key in ("h2h_over_2_5_prior", "h2h_btts_prior"):
        value = feature_data[key]
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"ML config features.{key} must be in [0, 1]")
    for key in ("expected_home_goals_multiplier", "referee_cards_scale", "rest_days_max"):
        value = feature_data[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"ML config features.{key} must be positive")
    value = feature_data["referee_avg_reds_prior"]
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("ML config features.referee_avg_reds_prior must be nonnegative")
    teams = feature_data["top_teams"]
    derbies = feature_data["derbies"]
    if not isinstance(teams, list) or any(not isinstance(team, str) or not team for team in teams) or len(teams) != len(set(teams)):
        raise ValueError("ML config features.top_teams must contain unique team names")
    if not isinstance(derbies, list) or any(
        not isinstance(pair, list) or len(pair) != 2 or
        any(not isinstance(team, str) or not team for team in pair) or pair[0] == pair[1]
        for pair in derbies
    ):
        raise ValueError("ML config features.derbies must contain pairs of distinct team names")
    cv_data = _section(data, "cv", set(CVConfig.__dataclass_fields__))
    stack_data = _section(data, "stacking", set(StackingConfig.__dataclass_fields__))
    for key, value in cv_data.items():
        _positive_int(value, f"cv.{key}", minimum=0 if key == "gap_rounds" else 1)
    for key in ("min_calibration_matches", "min_base_matches", "max_oof_folds", "min_matches_per_oof_fold", "meta_max_iter"):
        _positive_int(stack_data[key], f"stacking.{key}", minimum=2 if key == "max_oof_folds" else 1)
    if type(stack_data["calibration_fraction"]) not in (int, float) or not math.isfinite(stack_data["calibration_fraction"]) or not 0 < stack_data["calibration_fraction"] < 1:
        raise ValueError("ML config stacking.calibration_fraction must be between 0 and 1")
    if type(stack_data["meta_c"]) not in (int, float) or not math.isfinite(stack_data["meta_c"]) or stack_data["meta_c"] <= 0:
        raise ValueError("ML config stacking.meta_c must be positive")
    estimators = _section(data, "estimators", {"xgboost", "lightgbm", "catboost"})
    if any(not isinstance(params, dict) or not params for params in estimators.values()):
        raise ValueError("Each estimator requires a nonempty parameter mapping")
    return MLConfig(data["model_name"], data["random_seed"], elo, FeatureConfig(**feature_data), CVConfig(**cv_data), StackingConfig(**stack_data), estimators)


def load_ml_config(path: str | Path | None = None) -> MLConfig:
    """Read JSON from --config, ML_CONFIG_PATH, or the packaged default."""
    config_path = Path(path or os.getenv("ML_CONFIG_PATH") or DEFAULT_PATH)
    with config_path.open(encoding="utf-8") as stream:
        return parse_ml_config(json.load(stream))
