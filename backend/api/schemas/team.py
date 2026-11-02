# api/schemas/team.py
"""Team-related response schemas."""

from typing import Optional, List
from pydantic import BaseModel


class TeamSchema(BaseModel):
    id: int
    name: str
    short_name: Optional[str] = None
    logo_url: Optional[str] = None
    established_year: Optional[int] = None
    stadium_name: Optional[str] = None
    stadium_capacity: Optional[int] = None


class TeamFormEntry(BaseModel):
    match_id: int
    match_date: str
    opponent_name: str
    location: str          # "Home" | "Away"
    goals_scored: int
    goals_conceded: int
    outcome: str           # "W" | "D" | "L"
    points: int


class TeamSeasonStats(BaseModel):
    season_name: str
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_scored: int
    goals_conceded: int
    points: int
    ppg: float
    clean_sheets: int
    current_elo: Optional[float] = None


class TeamSeasonSplitStats(BaseModel):
    """Aggregated stats with overall/home/away splits."""
    played: int
    wins: int
    draws: int
    losses: int
    goals_scored: int
    goals_conceded: int
    goal_difference: int
    points: int
    win_rate: float
    avg_goals_scored: float
    avg_goals_conceded: float


class TeamDetailSchema(TeamSchema):
    current_season_stats: Optional[TeamSeasonStats] = None
    last_5_form: Optional[List[TeamFormEntry]] = None


class TeamFormResponse(BaseModel):
    """Response for GET /teams/{id}/form."""
    team: "TeamBriefSchema"
    form: List[TeamFormEntry]
    form_string: str       # e.g. "WWDLW"
    points_last_5: int


class TeamStatsResponse(BaseModel):
    """Response for GET /teams/{id}/stats with home/away splits."""
    team: "TeamBriefSchema"
    season: Optional["SeasonBrief"] = None
    overall: TeamSeasonSplitStats
    home: TeamSeasonSplitStats
    away: TeamSeasonSplitStats


class SeasonBrief(BaseModel):
    id: Optional[int] = None
    name: str


class H2HResponse(BaseModel):
    home_team: "TeamBriefSchema"
    away_team: "TeamBriefSchema"
    total_meetings: int
    home_wins: int
    draws: int
    away_wins: int
    avg_home_goals: float
    avg_away_goals: float
    over_2_5_rate: float
    btts_rate: float
    recent_matches: List["MatchListItem"]

# Avoid circular import
from api.schemas.match import MatchListItem, TeamBriefSchema  # noqa: E402
H2HResponse.model_rebuild()
TeamFormResponse.model_rebuild()
TeamStatsResponse.model_rebuild()
