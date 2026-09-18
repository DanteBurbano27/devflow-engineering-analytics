"""Dependency composition and local orchestration for repository ingestion."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from ingestion.common.config import ConfigurationError, Settings
from ingestion.common.logging import configure_logging
from ingestion.github.client import GitHubClient
from ingestion.github.repository_batch import (
    GitHubRepositoryBatch,
    RepositoryBatchConfigurationError,
    RepositoryBatchResult,
    load_repository_config,
)
from ingestion.github.repository_service import GitHubRepositoryService

type Clock = Callable[[], datetime]


class PipelineStatus(StrEnum):
    """Terminal status of one pipeline execution."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class PipelineStageStatus(StrEnum):
    """Status of one pipeline stage."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class PipelineStageResult:
    """Automation-safe result for one pipeline stage."""

    name: str
    status: PipelineStageStatus

    def to_record(self) -> dict[str, str]:
        """Return a JSON-serializable representation."""
        return {"name": self.name, "status": self.status.value}


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Stable result returned by every pipeline execution."""

    run_id: str
    started_at: datetime
    extracted_at: datetime
    status: PipelineStatus
    repositories_succeeded: int
    repositories_failed: int
    manifest_path: Path | None
    stages: tuple[PipelineStageResult, ...]
    error_type: str | None = None
    error_message: str | None = None

    @property
    def exit_code(self) -> int:
        """Map terminal status to a process exit code."""
        return {
            PipelineStatus.SUCCESS: 0,
            PipelineStatus.PARTIAL_SUCCESS: 2,
            PipelineStatus.FAILED: 1,
        }[self.status]

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-serializable, secret-safe result."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "extracted_at": self.extracted_at.isoformat(),
            "status": self.status.value,
            "exit_code": self.exit_code,
            "repositories_succeeded": self.repositories_succeeded,
            "repositories_failed": self.repositories_failed,
            "manifest_path": (
                str(self.manifest_path) if self.manifest_path is not None else None
            ),
            "stages": [stage.to_record() for stage in self.stages],
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


def run_pipeline(
    *,
    config_path: Path,
    output_root: Path,
    clock: Clock | None = None,
) -> PipelineResult:
    """Run configuration through GitHub extraction and local persistence."""
    pipeline_clock = clock or _utc_now
    started_at = _read_utc_clock(pipeline_clock, field_name="started_at")
    extracted_at = _read_utc_clock(pipeline_clock, field_name="extracted_at")
    run_id = extracted_at.strftime("%Y%m%dT%H%M%S%fZ")
    stages: list[PipelineStageResult] = []

    try:
        repository_config = load_repository_config(Path(config_path))
        settings = Settings.from_env()
        configure_logging(settings.log_level)
    except (ConfigurationError, RepositoryBatchConfigurationError) as exc:
        stages.append(_stage("configuration", PipelineStageStatus.FAILED))
        stages.extend(_skipped_stages("client", "service", "batch"))
        return _failed_result(
            run_id=run_id,
            started_at=started_at,
            extracted_at=extracted_at,
            stages=stages,
            error=exc,
            message=str(exc),
        )

    stages.append(_stage("configuration", PipelineStageStatus.SUCCESS))

    try:
        client = GitHubClient(
            token=settings.github_token,
            base_url=settings.github_api_base_url,
            api_version=settings.github_api_version,
            timeout_seconds=settings.github_timeout_seconds,
            max_retries=settings.github_max_retries,
            backoff_seconds=settings.github_backoff_seconds,
        )
    except (TypeError, ValueError) as exc:
        stages.append(_stage("client", PipelineStageStatus.FAILED))
        stages.extend(_skipped_stages("service", "batch"))
        return _failed_result(
            run_id=run_id,
            started_at=started_at,
            extracted_at=extracted_at,
            stages=stages,
            error=exc,
            message="GitHub client configuration is invalid.",
        )

    stages.append(_stage("client", PipelineStageStatus.SUCCESS))
    service = GitHubRepositoryService(client)
    stages.append(_stage("service", PipelineStageStatus.SUCCESS))

    batch_clock = _BatchClock(
        started_at=started_at,
        extracted_at=extracted_at,
        completion_clock=pipeline_clock,
    )

    try:
        batch_result = GitHubRepositoryBatch(service, clock=batch_clock).run(
            repository_config,
            output_root=Path(output_root),
        )
    except OSError as exc:
        stages.append(_stage("batch", PipelineStageStatus.FAILED))
        return _failed_result(
            run_id=run_id,
            started_at=started_at,
            extracted_at=extracted_at,
            stages=stages,
            error=exc,
            message="Pipeline outputs could not be published.",
        )

    stages.append(_stage("batch", PipelineStageStatus.SUCCESS))
    return _successful_result(
        batch_result=batch_result,
        started_at=started_at,
        extracted_at=extracted_at,
        stages=stages,
    )


class _BatchClock:
    """Give the batch the pipeline timestamps, then a live completion time."""

    def __init__(
        self,
        *,
        started_at: datetime,
        extracted_at: datetime,
        completion_clock: Clock,
    ) -> None:
        self._initial_values: Iterator[datetime] = iter((started_at, extracted_at))
        self._completion_clock = completion_clock

    def __call__(self) -> datetime:
        """Return shared context values before delegating completion time."""
        try:
            return next(self._initial_values)
        except StopIteration:
            return self._completion_clock()


def _utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(UTC)


def _read_utc_clock(clock: Clock, *, field_name: str) -> datetime:
    """Read one timezone-aware clock value and normalize it to UTC."""
    value = clock()
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} clock value must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} clock value must include timezone information.")
    return value.astimezone(UTC)


def _stage(name: str, status: PipelineStageStatus) -> PipelineStageResult:
    """Build one stage result."""
    return PipelineStageResult(name=name, status=status)


def _skipped_stages(*names: str) -> list[PipelineStageResult]:
    """Build skipped results for stages that could not run."""
    return [_stage(name, PipelineStageStatus.SKIPPED) for name in names]


def _failed_result(
    *,
    run_id: str,
    started_at: datetime,
    extracted_at: datetime,
    stages: list[PipelineStageResult],
    error: Exception,
    message: str,
) -> PipelineResult:
    """Build a failed result without copying unsafe exception details."""
    return PipelineResult(
        run_id=run_id,
        started_at=started_at,
        extracted_at=extracted_at,
        status=PipelineStatus.FAILED,
        repositories_succeeded=0,
        repositories_failed=0,
        manifest_path=None,
        stages=tuple(stages),
        error_type=type(error).__name__,
        error_message=message,
    )


def _successful_result(
    *,
    batch_result: RepositoryBatchResult,
    started_at: datetime,
    extracted_at: datetime,
    stages: list[PipelineStageResult],
) -> PipelineResult:
    """Adapt a repository batch result to the public pipeline contract."""
    return PipelineResult(
        run_id=batch_result.run_id,
        started_at=started_at,
        extracted_at=extracted_at,
        status=PipelineStatus(batch_result.status),
        repositories_succeeded=batch_result.repositories_succeeded,
        repositories_failed=batch_result.repositories_failed,
        manifest_path=batch_result.manifest_path,
        stages=tuple(stages),
    )
