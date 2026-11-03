# api/schemas/prediction.py
"""Prediction request/response schemas."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, Optional, List
from pydantic import BaseModel, Field, model_validator


class PredictRequest(BaseModel):
    """
    Input for a prediction request.

    Provide EITHER match_id (for a known DB match) OR
    home_team_id + away_team_id + match_datetime + season_name + match_week for a custom fixture.
    """
    match_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Internal match ID from /api/v1/matches. Use for upcoming fixtures already in DB.",
    )
    home_team_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Internal team ID. Required if match_id is not provided.",
    )
    away_team_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Internal team ID. Required if match_id is not provided.",
    )
    match_datetime: Optional[str] = Field(
        default=None,
        description="ISO 8601 datetime for the fixture. Required if match_id is not provided.",
        examples=["2024-08-17T15:00:00Z"],
    )
    season_name: Optional[str] = Field(
        default=None,
        description="Canonical season name stored in the database, such as 2024/2025.",
        examples=["2024/2025"],
    )
    match_week: Optional[int] = Field(
        default=None,
        ge=1,
        le=38,
        description="Premier League matchweek. Required for a custom fixture.",
    )
    include_feature_breakdown: bool = Field(
        default=False,
        description="If true, includes the raw feature vector in the response (for debugging).",
    )

    @model_validator(mode="after")
    def validate_inputs(self) -> "PredictRequest":
        if self.match_id is not None:
            if any(value is not None for value in (
                self.home_team_id, self.away_team_id, self.match_datetime,
                self.season_name, self.match_week,
            )):
                raise ValueError("Provide match_id or custom fixture fields, not both.")
        else:
            if self.home_team_id is None or self.away_team_id is None:
                raise ValueError(
                    "Provide either 'match_id' or both 'home_team_id' and 'away_team_id'."
                )
            if self.home_team_id == self.away_team_id:
                raise ValueError("home_team_id and away_team_id must be different.")
            if not self.match_datetime:
                raise ValueError("match_datetime is required for a custom fixture.")
            try:
                kickoff = datetime.fromisoformat(self.match_datetime.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("match_datetime must be a valid ISO 8601 datetime.") from exc
            if kickoff.tzinfo is None or kickoff.utcoffset() is None:
                raise ValueError("match_datetime must include a timezone offset.")
            if kickoff <= datetime.now(timezone.utc):
                raise ValueError("match_datetime must be in the future.")
            if not self.season_name:
                raise ValueError("season_name is required for a custom fixture.")
            if self.match_week is None:
                raise ValueError("match_week is required for a custom fixture.")
        return self


class ProbabilityBreakdown(BaseModel):
    home_win: float = Field(ge=0.0, le=1.0, description="P(Home Win)")
    draw: float     = Field(ge=0.0, le=1.0, description="P(Draw)")
    away_win: float = Field(ge=0.0, le=1.0, description="P(Away Win)")


class KeyFeatures(BaseModel):
    """Top features driving this prediction (SHAP-based)."""
    home_elo: Optional[float] = None
    away_elo: Optional[float] = None
    elo_diff: Optional[float] = None
    home_form5_ppg: Optional[float] = None
    away_form5_ppg: Optional[float] = None
    h2h_home_win_rate: Optional[float] = None
    home_season_ppg: Optional[float] = None
    away_season_ppg: Optional[float] = None
    home_absences: Optional[int] = None
    away_absences: Optional[int] = None


class PredictResponse(BaseModel):
    match_id: Optional[int] = None
    home_team_id: int
    away_team_id: int
    home_team_name: str
    away_team_name: str
    match_datetime: Optional[str] = None

    probabilities: ProbabilityBreakdown
    predicted_outcome: str           # "H" | "D" | "A"
    confidence: float = Field(ge=0.0, le=1.0)

    model_version: str
    key_features: Optional[KeyFeatures] = None
    feature_vector: Optional[Dict[str, float]] = None


class PredictionRecord(BaseModel):
    """Stored prediction record (for GET /predictions)."""
    id: int
    match_id: int
    home_team_name: str
    away_team_name: str
    predicted_outcome: str
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    actual_outcome: Optional[str] = None
    was_correct: Optional[bool] = None
    created_at: str
