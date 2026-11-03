"""Model endpoints must use the loaded predictor through the service contract."""

from fastapi.testclient import TestClient

from api.dependencies import get_prediction_service
from api.main import create_app
from api.services.prediction_service import PredictionService


def test_model_endpoints_with_loaded_artifact():
    service = PredictionService()
    service._predictor.model = object()
    service._predictor.metadata = {
        "version": "test-version",
        "training_seasons": ["2024/2025"],
    }
    service._predictor.feature_names = ["elo_diff"]

    app = create_app()
    app.dependency_overrides[get_prediction_service] = lambda: service
    client = TestClient(app)

    info = client.get("/api/v1/model/info")
    features = client.get("/api/v1/model/features")

    assert info.status_code == 200
    assert info.json()["version"] == "test-version"
    assert info.json()["feature_names"] == ["elo_diff"]
    assert features.status_code == 200
    assert features.json() == {
        "loaded": True,
        "n_features": 1,
        "features": ["elo_diff"],
    }
