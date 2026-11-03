from types import SimpleNamespace

import pytest

from elt_pipeline.orchestrator import ETLOrchestrator


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
