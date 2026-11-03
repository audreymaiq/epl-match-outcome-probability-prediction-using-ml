"""HTTP prediction routes must preserve their read and write semantics."""

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from api.dependencies import get_db, get_prediction_service
from api.main import create_app
from api.services.prediction_service import PredictionService


def test_get_prediction_does_not_save_but_post_does(monkeypatch):
    service = PredictionService()
    service._predictor.model = object()
    service._predictor.metadata = {"version": "test-version"}
    service._predictor.feature_names = ["elo_diff"]
    monkeypatch.setattr(service, "_extract_features", lambda *_: (
        pd.DataFrame({"elo_diff": [0.0]}),
        {
            "match_id": 17,
            "home_team_id": 1,
            "away_team_id": 2,
            "home_team_name": "Home",
            "away_team_name": "Away",
            "match_datetime": "2027-01-01T12:00:00Z",
        },
    ))
    monkeypatch.setattr(service._predictor, "predict", lambda *_: (
        np.array([[0.0]]), np.array([0.5, 0.3, 0.2]),
    ))
    saved = []
    monkeypatch.setattr(service, "_save_prediction", lambda *_: saved.append(17))

    app = create_app()
    app.dependency_overrides[get_prediction_service] = lambda: service
    app.dependency_overrides[get_db] = lambda: object()
    client = TestClient(app)

    get_response = client.get("/api/v1/predictions/model-probabilities/17")
    assert get_response.status_code == 200
    assert saved == []

    post_response = client.post("/api/v1/predictions", json={"match_id": 17})
    assert post_response.status_code == 200
    assert saved == [17]
