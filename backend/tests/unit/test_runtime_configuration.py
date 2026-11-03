"""Regression checks for serving and provider runtime configuration."""

from fastapi.testclient import TestClient

from api.main import create_app
from config.settings import ScrapingSettings, SofascoreSettings


def test_metrics_middleware_handles_fastapi_routes(monkeypatch):
    monkeypatch.setenv("ENABLE_METRICS", "true")

    response = TestClient(create_app()).get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"]


def test_scraping_settings_read_environment(monkeypatch):
    monkeypatch.setenv("SCRAPING_CONNECT_TIMEOUT", "8")
    monkeypatch.setenv("SCRAPING_MIN_DELAY", "0.25")
    monkeypatch.setenv("SCRAPING_MAX_DELAY", "0.5")

    settings = ScrapingSettings(_env_file=None)

    assert settings.connect_timeout == 8
    assert settings.is_configured
    assert 0.25 <= settings.get_random_delay() <= 0.5


def test_sofascore_settings_have_valid_defaults():
    assert SofascoreSettings(_env_file=None).is_configured
