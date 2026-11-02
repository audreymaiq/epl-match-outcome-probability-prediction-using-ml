# api/schemas/__init__.py
from api.schemas.common import HealthStatus, PagedResponse, Pagination, ErrorResponse
from api.schemas.match import MatchListItem, MatchDetail, TeamBriefSchema
from api.schemas.prediction import PredictRequest, PredictResponse, ProbabilityBreakdown
from api.schemas.team import TeamSchema, TeamDetailSchema, TeamSeasonStats, H2HResponse

__all__ = [
    "HealthStatus", "PagedResponse", "Pagination", "ErrorResponse",
    "MatchListItem", "MatchDetail", "TeamBriefSchema",
    "PredictRequest", "PredictResponse", "ProbabilityBreakdown",
    "TeamSchema", "TeamDetailSchema", "TeamSeasonStats", "H2HResponse",
]

