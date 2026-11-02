# api/schemas/match.py
"""Match-related response schemas."""

from typing import Optional, List
from pydantic import BaseModel


class StadiumSchema(BaseModel):
    id: int
    name: str
    city: Optional[str] = None
    capacity: Optional[int] = None


class TeamBriefSchema(BaseModel):
    id: int
    name: str
    short_name: Optional[str] = None
    logo_url: Optional[str] = None


class RefereeSchema(BaseModel):
    id: int
    name: str
    country: Optional[str] = None


class MatchListItem(BaseModel):
    id: int
    season_name: str
    match_datetime: str
    match_week: Optional[str] = None
    home_team: TeamBriefSchema
    away_team: TeamBriefSchema
    status: str
    outcome: Optional[str] = None
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None


class MatchDetail(MatchListItem):
    """Extends MatchListItem with full match details."""
    half_time_home_goals: Optional[int] = None
    half_time_away_goals: Optional[int] = None
    stadium: Optional[StadiumSchema] = None
    referee: Optional[RefereeSchema] = None
    attendance: Optional[int] = None
    home_possession: Optional[float] = None
    away_possession: Optional[float] = None
    home_shots: Optional[int] = None
    away_shots: Optional[int] = None
    home_shots_on_target: Optional[int] = None
    away_shots_on_target: Optional[int] = None
    home_corners: Optional[int] = None
    away_corners: Optional[int] = None
