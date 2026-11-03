"""Empty collections must report zero pages consistently."""

from fastapi.testclient import TestClient

from api.dependencies import get_db
from api.main import create_app
from api.services.match_service import MatchService
from api.services.team_service import TeamService


def test_empty_match_and_team_collections_have_zero_pages(monkeypatch):
    monkeypatch.setattr(MatchService, "list_matches", lambda *_args, **_kwargs: ([], 0))
    monkeypatch.setattr(TeamService, "list_teams", lambda *_args, **_kwargs: ([], 0))

    app = create_app()
    app.dependency_overrides[get_db] = lambda: object()
    client = TestClient(app)

    for path in ("/api/v1/matches", "/api/v1/teams"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["pagination"] == {
            "page": 1,
            "page_size": 20 if path.endswith("matches") else 50,
            "total": 0,
            "total_pages": 0,
        }
