# api/routers/matches.py
"""Match endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.dependencies import get_db, get_competition_dep
from api.services.match_service import MatchService
from api.schemas.match import MatchListItem, MatchDetail
from api.schemas.common import PagedResponse, Pagination

router = APIRouter(prefix="/matches", tags=["Matches"])


@router.get("/seasons", response_model=list[str], summary="Available seasons")
def list_seasons(db: Session = Depends(get_db), competition=Depends(get_competition_dep)) -> list[str]:
    rows = db.execute(text('SELECT s.name FROM "Seasons" s JOIN "Leagues" l ON l.id=s.league_id WHERE l.slug=:slug ORDER BY s.start_year DESC'), {"slug": competition.slug}).scalars()
    return list(rows)


@router.get(
    "",
    response_model=PagedResponse[MatchListItem],
    summary="List matches with optional filters",
)
def list_matches(
    season: Optional[str] = Query(None, description='e.g. "2023/24"'),
    status: Optional[str] = Query(None, description="FINISHED | SCHEDULED | POSTPONED"),
    team_id: Optional[int] = Query(None, ge=1, description="Only matches involving this team"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    competition=Depends(get_competition_dep),
):
    svc = MatchService(db, competition=competition)
    items, total = svc.list_matches(
        season_name=season, status=status, team_id=team_id, page=page, page_size=page_size
    )
    total_pages = -(-total // page_size)
    return PagedResponse(
        data=items,
        pagination=Pagination(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


@router.get(
    "/{match_id}",
    response_model=MatchDetail,
    summary="Get full match detail",
)
def get_match(match_id: int, db: Session = Depends(get_db), competition=Depends(get_competition_dep)):
    svc = MatchService(db, competition=competition)
    return svc.get_match_detail(match_id)

