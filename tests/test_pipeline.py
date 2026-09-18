"""Tests for local DevFlow pipeline orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from ingestion.github.repository_batch import (
    RepositoryBatchConfigurationError,
    RepositoryBatchResult,
)
from orchestration import pipeline


def sequence_clock(values: list[datetime]):
    """Return a deterministic clock over the provided values."""
    iterator = iter(values)
    return lambda: next(iterator)


def test_pipeline_composes_dependencies_with_one_shared_run_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Every batch layer must receive the run timestamp owned by orchestration."""
    started_at = datetime(2026, 9, 18, 10, 0, 0, tzinfo=UTC)
    extracted_at = datetime(2026, 9, 18, 10, 0, 1, 123456, tzinfo=UTC)
    completed_at = datetime(2026, 9, 18, 10, 0, 2, tzinfo=UTC)
    expected_run_id = "20260918T100001123456Z"
    config = object()
    client = object()
    service = object()
    observed: dict[str, object] = {}
    settings = SimpleNamespace(
        github_token="test-token",
        github_api_base_url="https://example.invalid",
        github_api_version="test-version",
        github_timeout_seconds=1.0,
        github_max_retries=0,
        github_backoff_seconds=0.0,
        log_level="INFO",
    )

    monkeypatch.setattr(pipeline, "load_repository_config", lambda path: config)
    monkeypatch.setattr(pipeline.Settings, "from_env", lambda: settings)
    monkeypatch.setattr(
        pipeline,
        "configure_logging",
        lambda level: observed.update(log_level=level),
    )

    def build_client(**kwargs: object) -> object:
        observed["client_kwargs"] = kwargs
        return client

    def build_service(received_client: object) -> object:
        observed["service_client"] = received_client
        return service

    class FakeBatch:
        def __init__(self, received_service: object, *, clock) -> None:
            observed["batch_service"] = received_service
            observed["batch_times"] = [clock(), clock(), clock()]

        def run(self, received_config: object, *, output_root: Path):
            observed["batch_config"] = received_config
            observed["output_root"] = output_root
            return RepositoryBatchResult(
                run_id=expected_run_id,
                status="success",
                repositories_succeeded=2,
                repositories_failed=0,
                output_root=output_root,
                manifest_path=output_root / "manifest.json",
            )

    monkeypatch.setattr(pipeline, "GitHubClient", build_client)
    monkeypatch.setattr(pipeline, "GitHubRepositoryService", build_service)
    monkeypatch.setattr(pipeline, "GitHubRepositoryBatch", FakeBatch)

    result = pipeline.run_pipeline(
        config_path=tmp_path / "repositories.json",
        output_root=tmp_path / "data",
        clock=sequence_clock([started_at, extracted_at, completed_at]),
    )

    assert result.status == pipeline.PipelineStatus.SUCCESS
    assert result.exit_code == 0
    assert result.run_id == expected_run_id
    assert result.extracted_at == extracted_at
    assert result.repositories_succeeded == 2
    assert observed["service_client"] is client
    assert observed["batch_service"] is service
    assert observed["batch_config"] is config
    assert observed["batch_times"] == [started_at, extracted_at, completed_at]
    assert [stage.to_record() for stage in result.stages] == [
        {"name": "configuration", "status": "success"},
        {"name": "client", "status": "success"},
        {"name": "service", "status": "success"},
        {"name": "batch", "status": "success"},
    ]


def test_pipeline_configuration_failure_skips_dependent_stages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Invalid repository configuration must fail before credentials are loaded."""
    times = [
        datetime(2026, 9, 18, 11, 0, 0, tzinfo=UTC),
        datetime(2026, 9, 18, 11, 0, 1, tzinfo=UTC),
    ]
    settings_loaded = False

    def fail_config(path: Path) -> object:
        raise RepositoryBatchConfigurationError("invalid repository configuration")

    def load_settings() -> object:
        nonlocal settings_loaded
        settings_loaded = True
        raise AssertionError("settings must not be loaded")

    monkeypatch.setattr(pipeline, "load_repository_config", fail_config)
    monkeypatch.setattr(pipeline.Settings, "from_env", load_settings)

    result = pipeline.run_pipeline(
        config_path=tmp_path / "invalid.json",
        output_root=tmp_path / "data",
        clock=sequence_clock(times),
    )

    assert settings_loaded is False
    assert result.status == pipeline.PipelineStatus.FAILED
    assert result.exit_code == 1
    assert result.error_type == "RepositoryBatchConfigurationError"
    assert result.error_message == "invalid repository configuration"
    assert [stage.status for stage in result.stages] == [
        pipeline.PipelineStageStatus.FAILED,
        pipeline.PipelineStageStatus.SKIPPED,
        pipeline.PipelineStageStatus.SKIPPED,
        pipeline.PipelineStageStatus.SKIPPED,
    ]


@pytest.mark.parametrize(
    ("batch_status", "expected_status", "expected_exit_code"),
    [
        ("partial_success", pipeline.PipelineStatus.PARTIAL_SUCCESS, 2),
        ("failed", pipeline.PipelineStatus.FAILED, 1),
    ],
)
def test_pipeline_preserves_batch_terminal_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    batch_status: str,
    expected_status: pipeline.PipelineStatus,
    expected_exit_code: int,
) -> None:
    """Partial and failed batches must remain distinguishable to automation."""
    started_at = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    extracted_at = datetime(2026, 9, 18, 12, 0, 1, tzinfo=UTC)
    completed_at = datetime(2026, 9, 18, 12, 0, 2, tzinfo=UTC)
    settings = SimpleNamespace(
        github_token="test-token",
        github_api_base_url="https://example.invalid",
        github_api_version="test-version",
        github_timeout_seconds=1.0,
        github_max_retries=0,
        github_backoff_seconds=0.0,
        log_level="INFO",
    )

    monkeypatch.setattr(pipeline, "load_repository_config", lambda path: object())
    monkeypatch.setattr(pipeline.Settings, "from_env", lambda: settings)
    monkeypatch.setattr(pipeline, "configure_logging", lambda level: None)
    monkeypatch.setattr(pipeline, "GitHubClient", lambda **kwargs: object())
    monkeypatch.setattr(pipeline, "GitHubRepositoryService", lambda client: object())

    class FakeBatch:
        def __init__(self, service: object, *, clock) -> None:
            self.clock = clock

        def run(self, config: object, *, output_root: Path):
            self.clock()
            self.clock()
            self.clock()
            return RepositoryBatchResult(
                run_id="20260918T120001000000Z",
                status=batch_status,
                repositories_succeeded=int(batch_status == "partial_success"),
                repositories_failed=1,
                output_root=output_root,
                manifest_path=output_root / "manifest.json",
            )

    monkeypatch.setattr(pipeline, "GitHubRepositoryBatch", FakeBatch)

    result = pipeline.run_pipeline(
        config_path=tmp_path / "repositories.json",
        output_root=tmp_path / "data",
        clock=sequence_clock([started_at, extracted_at, completed_at]),
    )

    assert result.status == expected_status
    assert result.exit_code == expected_exit_code


def test_pipeline_output_failure_does_not_expose_exception_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Unexpected filesystem messages must not leak into automation output."""
    secret = "Authorization: Bearer simulated-token"
    times = [
        datetime(2026, 9, 18, 13, 0, 0, tzinfo=UTC),
        datetime(2026, 9, 18, 13, 0, 1, tzinfo=UTC),
    ]
    settings = SimpleNamespace(
        github_token="test-token",
        github_api_base_url="https://example.invalid",
        github_api_version="test-version",
        github_timeout_seconds=1.0,
        github_max_retries=0,
        github_backoff_seconds=0.0,
        log_level="INFO",
    )
    monkeypatch.setattr(pipeline, "load_repository_config", lambda path: object())
    monkeypatch.setattr(pipeline.Settings, "from_env", lambda: settings)
    monkeypatch.setattr(pipeline, "configure_logging", lambda level: None)
    monkeypatch.setattr(pipeline, "GitHubClient", lambda **kwargs: object())
    monkeypatch.setattr(pipeline, "GitHubRepositoryService", lambda client: object())

    class FailingBatch:
        def __init__(self, service: object, *, clock) -> None:
            pass

        def run(self, config: object, *, output_root: Path):
            raise OSError(secret)

    monkeypatch.setattr(pipeline, "GitHubRepositoryBatch", FailingBatch)

    result = pipeline.run_pipeline(
        config_path=tmp_path / "repositories.json",
        output_root=tmp_path / "data",
        clock=sequence_clock(times),
    )

    serialized = result.to_record()
    assert serialized["error_message"] == "Pipeline outputs could not be published."
    assert secret not in str(serialized)
