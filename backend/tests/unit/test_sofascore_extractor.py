"""SofaScore HTTP failures must be visible to the pipeline operator."""

from types import SimpleNamespace

import pytest
from curl_cffi.requests.exceptions import HTTPError

from config.settings import ScrapingSettings, SofascoreSettings
from providers.sofascore.extractor import SofaScoreExtractor


def test_access_denied_is_reported_without_retry(monkeypatch):
    extractor = SofaScoreExtractor(
        SofascoreSettings(_env_file=None), ScrapingSettings(_env_file=None)
    )
    attempts = 0

    def reject(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        raise HTTPError("Forbidden", response=SimpleNamespace(status_code=403))

    monkeypatch.setattr(extractor, "_rate_limit", lambda: None)
    monkeypatch.setattr(extractor.session, "get", reject)
    try:
        with pytest.raises(RuntimeError, match="HTTP 403"):
            extractor.fetch_seasons(17)
        assert attempts == 1
    finally:
        extractor.close()
