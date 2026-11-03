from types import SimpleNamespace

import pytest

from elt_pipeline.orchestrator import ETLOrchestrator, run_pipeline


class FakeProvider:
    name = "test"

    def health_check(self):
        return True

    def fetch_season_matches(self, tournament_id, season_id):
        return [SimpleNamespace(external_id=match_id) for match_id in range(51)]

    def fetch_match_bundle(self, match_id):
        return {"match_id": match_id}


class FakeTransformer:
    provider_name = "test"

    def transform(self, raw_bundle):
        return raw_bundle


def test_provider_and_transformer_must_match():
    transformer = FakeTransformer()
    transformer.provider_name = "different"

    with pytest.raises(ValueError, match="mismatch"):
        ETLOrchestrator(FakeProvider(), transformer)


def test_process_season_counts_all_flushed_batches(monkeypatch):
    orchestrator = ETLOrchestrator(FakeProvider(), FakeTransformer(), batch_size=50)
    monkeypatch.setattr(
        orchestrator,
        "_load_batch",
        lambda bundles: {"success": len(bundles), "failed": 0, "total": len(bundles)},
    )

    result = orchestrator.process_season(1, 1, "2025/26")

    assert result["total"] == 51
    assert result["success"] == 51
    assert result["failed"] == 0


@pytest.fixture
def pipeline_provider(monkeypatch):
    import config.settings
    import elt_pipeline.orchestrator as module
    from providers.base.provider_registry import ProviderRegistry
    from utils.db_connector import DatabaseConnector

    class PipelineProvider(FakeProvider):
        tournament_id = 17

        def __init__(self):
            self.closed = False

        def list_seasons(self):
            return [("2024/2025", 1)]

        def close(self):
            self.closed = True

    provider = PipelineProvider()
    monkeypatch.setattr(module, "discover_providers", lambda: None)
    monkeypatch.setattr(module.signal, "signal", lambda *_: None)
    monkeypatch.setattr(config.settings, "get_config", lambda: SimpleNamespace(
        seasons=SimpleNamespace(seasons_to_fetch=7),
    ))
    monkeypatch.setattr(ProviderRegistry, "is_registered", lambda *_: True)
    monkeypatch.setattr(ProviderRegistry, "create", lambda *_: provider)
    monkeypatch.setattr(ProviderRegistry, "create_transformer", lambda *_: FakeTransformer())
    monkeypatch.setattr(DatabaseConnector, "check_connection", lambda: True)
    return provider


@pytest.mark.parametrize("requested", [["1990/1991"], ["2024/2025", "1990/1991"]])
def test_pipeline_fails_when_requested_season_is_missing(pipeline_provider, requested):
    result = run_pipeline("test", requested)

    assert result["success"] is False
    assert result["total_seasons"] == 0
    assert pipeline_provider.closed


def test_pipeline_fails_when_one_match_cannot_be_loaded(monkeypatch, pipeline_provider):
    monkeypatch.setattr(ETLOrchestrator, "process_season", lambda *_: {
        "season_name": "2024/2025", "total": 2, "success": 1, "failed": 1,
    })

    result = run_pipeline("test")

    assert result["success"] is False
    assert result["total_matches"] == 2
    assert result["successful_matches"] == 1
    assert pipeline_provider.closed
