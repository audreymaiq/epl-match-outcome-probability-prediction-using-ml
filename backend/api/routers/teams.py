# api/routers/teams.py
"""Team endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.services.team_service import TeamService
from api.schemas.team import (
    TeamSchema, TeamDetailSchema, TeamFormResponse, TeamStatsResponse, H2HResponse,
)
from api.schemas.common import PagedResponse, Pagination

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get(
    "",
    response_model=PagedResponse[TeamSchema],
    summary="List all EPL teams",
)
def list_teams(
    search: Optional[str] = Query(None, description="Search by team name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    svc = TeamService(db)
    items, total = svc.list_teams(search=search, page=page, page_size=page_size)
    total_pages = -(-total // page_size)
    return PagedResponse(
        data=items,
        pagination=Pagination(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


@router.get(
    "/head-to-head",
    response_model=H2HResponse,
    summary="Head-to-head statistics between two teams",
)
def head_to_head(
    home_team_id: int = Query(..., description="Internal ID of the home team"),
    away_team_id: int = Query(..., description="Internal ID of the away team"),
    db: Session = Depends(get_db),
):
    svc = TeamService(db)
    return svc.get_h2h(home_team_id, away_team_id)


@router.get(
    "/{team_id}",
    response_model=TeamDetailSchema,
    summary="Get team detail with season stats and form",
)
def get_team(
    team_id: int,
    season: Optional[str] = Query(None, description='Season name, e.g. "2023/24"'),
    db: Session = Depends(get_db),
):
    svc = TeamService(db)
    return svc.get_team_detail(team_id, season_name=season)


@router.get(
    "/{team_id}/form",
    response_model=TeamFormResponse,
    summary="Get team's last 5 match results",
)
def get_team_form(
    team_id: int,
    db: Session = Depends(get_db),
):
    svc = TeamService(db)
    return svc.get_team_form(team_id)


@router.get(
    "/{team_id}/stats",
    response_model=TeamStatsResponse,
    summary="Get team's season statistics (overall, home, away splits)",
)
def get_team_stats(
    team_id: int,
    season: Optional[str] = Query(None, description='Season name, e.g. "2023/24"'),
    db: Session = Depends(get_db),
):
    svc = TeamService(db)
    return svc.get_team_stats(team_id, season_name=season)
