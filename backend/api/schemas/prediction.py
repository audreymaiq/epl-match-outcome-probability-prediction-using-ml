# api/schemas/prediction.py
"""Prediction request/response schemas."""

from __future__ import annotations
from typing import Dict, Optional, List
from pydantic import BaseModel, Field, model_validator


class PredictRequest(BaseModel):
    """
    Input for a prediction request.

    Provide EITHER match_id (for a known DB match) OR
    home_team_id + away_team_id + match_datetime for a custom fixture.
    """
    match_id: Optional[int] = Field(
        default=None,
        description="Internal match ID from /api/v1/matches. Use for upcoming fixtures already in DB.",
    )
    home_team_id: Optional[int] = Field(
        default=None,
        description="Internal team ID. Required if match_id is not provided.",
    )
    away_team_id: Optional[int] = Field(
        default=None,
        description="Internal team ID. Required if match_id is not provided.",
    )
    match_datetime: Optional[str] = Field(
        default=None,
        description="ISO 8601 datetime for the fixture. Required if match_id is not provided.",
        examples=["2024-08-17T15:00:00Z"],
    )
    include_feature_breakdown: bool = Field(
        default=False,
        description="If true, includes the raw feature vector in the response (for debugging).",
    )

    @model_validator(mode="after")
    def validate_inputs(self) -> "PredictRequest":
        if self.match_id is None:
            if self.home_team_id is None or self.away_team_id is None:
                raise ValueError(
                    "Provide either 'match_id' or both 'home_team_id' and 'away_team_id'."
                )
            if self.home_team_id == self.away_team_id:
                raise ValueError("home_team_id and away_team_id must be different.")
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
