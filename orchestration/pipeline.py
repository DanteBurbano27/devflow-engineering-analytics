"""Dependency composition and local orchestration for repository ingestion."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from analytics.contracts.repository import ContractValidationError
from analytics.service import AnalyticsService, DataQualityValidationError
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

logger = logging.getLogger(__name__)


class PipelineStatus(StrEnum):
    """Terminal status of one pipeline execution."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class PipelineStageStatus(StrEnum):
    """Status of one pipeline stage."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
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
    raw_path: Path | None
    normalized_path: Path | None
    analytics_path: Path | None
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
            "raw_path": str(self.raw_path) if self.raw_path is not None else None,
            "normalized_path": (
                str(self.normalized_path) if self.normalized_path is not None else None
            ),
            "analytics_path": (
                str(self.analytics_path) if self.analytics_path is not None else None
            ),
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
        stages.extend(
            _skipped_stages("client", "service", "batch", "quality", "analytics")
        )
        return _failed_result(
            run_id=run_id,
            started_at=started_at,
            extracted_at=extracted_at,
            stages=stages,
            error=exc,
            message=str(exc),
        )

    stages.append(_stage("configuration", PipelineStageStatus.SUCCESS))
    logger.info(
        "DevFlow pipeline started.",
        extra={
            "operation": "devflow_pipeline",
            "run_id": run_id,
            "stage": "configuration",
            "status": "success",
        },
    )

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
        stages.extend(_skipped_stages("service", "batch", "quality", "analytics"))
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
        stages.extend(_skipped_stages("quality", "analytics"))
        return _failed_result(
            run_id=run_id,
            started_at=started_at,
            extracted_at=extracted_at,
            stages=stages,
            error=exc,
            message="Pipeline outputs could not be published.",
        )

    batch_stage_status = {
        "success": PipelineStageStatus.SUCCESS,
        "partial_success": PipelineStageStatus.PARTIAL_SUCCESS,
        "failed": PipelineStageStatus.FAILED,
    }[batch_result.status]
    stages.append(_stage("batch", batch_stage_status))

    if batch_result.repositories_succeeded == 0:
        stages.extend(_skipped_stages("quality", "analytics"))
        return _successful_result(
            batch_result=batch_result,
            started_at=started_at,
            extracted_at=extracted_at,
            stages=stages,
            analytics_path=None,
        )

    try:
        analytics_path = _run_analytics(
            batch_result=batch_result,
            extracted_at=extracted_at,
        )
    except _PipelineStageFailure as failure:
        if failure.stage == "quality":
            stages.append(_stage("quality", PipelineStageStatus.FAILED))
            stages.append(_stage("analytics", PipelineStageStatus.SKIPPED))
        else:
            stages.append(_stage("quality", PipelineStageStatus.SUCCESS))
            stages.append(_stage("analytics", PipelineStageStatus.FAILED))
        _record_pipeline_failure(
            batch_result=batch_result,
            failure_stage=failure.stage,
            error_type=type(failure.error).__name__,
        )
        logger.error(
            "DevFlow pipeline post-extraction stage failed.",
            extra={
                "operation": "devflow_pipeline",
                "run_id": run_id,
                "stage": failure.stage,
                "status": "failed",
                "error_type": type(failure.error).__name__,
            },
        )
        return _post_batch_failed_result(
            batch_result=batch_result,
            started_at=started_at,
            extracted_at=extracted_at,
            stages=stages,
            error=failure.error,
            failure_stage=failure.stage,
        )

    stages.append(_stage("quality", PipelineStageStatus.SUCCESS))
    stages.append(_stage("analytics", PipelineStageStatus.SUCCESS))
    logger.info(
        "DevFlow pipeline completed.",
        extra={
            "operation": "devflow_pipeline",
            "run_id": run_id,
            "stage": "analytics",
            "status": batch_result.status,
            "repositories_succeeded": batch_result.repositories_succeeded,
            "repositories_failed": batch_result.repositories_failed,
        },
    )
    return _successful_result(
        batch_result=batch_result,
        started_at=started_at,
        extracted_at=extracted_at,
        stages=stages,
        analytics_path=analytics_path,
    )


def _run_analytics(
    *,
    batch_result: RepositoryBatchResult,
    extracted_at: datetime,
) -> Path:
    """Validate normalized output, run quality and analytics, and publish a report."""
    try:
        records = _load_json_lines(batch_result.normalized_path)
    except (OSError, ValueError) as exc:
        raise _PipelineStageFailure("quality", exc) from exc

    try:
        metrics, quality_result, portfolio = AnalyticsService().process_batch(
            records,
            reference_time=extracted_at,
            fail_on_contract_error=True,
        )
        if not quality_result.is_valid:
            raise DataQualityValidationError(quality_result)
    except (ContractValidationError, DataQualityValidationError) as exc:
        raise _PipelineStageFailure("quality", exc) from exc

    analytics_path = (
        batch_result.output_root
        / "analytics"
        / "github"
        / "repositories"
        / f"extraction_date={extracted_at.date().isoformat()}"
        / f"run_id={batch_result.run_id}"
        / "report.json"
    )
    try:
        report = {
            "meta": {
                "run_id": batch_result.run_id,
                "generated_at": extracted_at.isoformat(),
                "total_input_records": len(records),
                "processed_records": len(metrics),
            },
            "quality": quality_result.to_dict(),
            "portfolio": portfolio.to_dict(),
            "repositories": [metric.to_dict() for metric in metrics],
        }
        _write_json_atomically(analytics_path, report)
        _enrich_manifest(
            batch_result=batch_result,
            analytics_path=analytics_path,
            analytics_records_written=len(metrics),
            quality_summary=quality_result.to_dict()["summary"],
        )
    except (OSError, TypeError, ValueError) as exc:
        raise _PipelineStageFailure("analytics", exc) from exc
    return analytics_path


class _PipelineStageFailure(Exception):
    """Carry a safe stage classification for an expected pipeline failure."""

    def __init__(self, stage: str, error: Exception) -> None:
        super().__init__(stage)
        self.stage = stage
        self.error = error


def _load_json_lines(path: Path) -> list[dict[str, Any]]:
    """Load normalized JSON Lines and require one object per non-empty line."""
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as normalized_file:
        for line_number, line in enumerate(normalized_file, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(
                    f"Normalized record at line {line_number} must be a JSON object."
                )
            records.append(record)
    return records


def _enrich_manifest(
    *,
    batch_result: RepositoryBatchResult,
    analytics_path: Path,
    analytics_records_written: int,
    quality_summary: dict[str, Any],
) -> None:
    """Publish analytics and quality evidence into the execution manifest."""
    with batch_result.manifest_path.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    if not isinstance(manifest, dict):
        raise ValueError("Execution manifest must be a JSON object.")

    manifest.update(
        {
            "pipeline_status": batch_result.status,
            "analytics_output": analytics_path.relative_to(
                batch_result.output_root
            ).as_posix(),
            "analytics_records_written": analytics_records_written,
            "quality": quality_summary,
        }
    )
    _write_json_atomically(batch_result.manifest_path, manifest, replace=True)


def _record_pipeline_failure(
    *,
    batch_result: RepositoryBatchResult,
    failure_stage: str,
    error_type: str,
) -> None:
    """Record the terminal pipeline failure without replacing extraction evidence."""
    try:
        with batch_result.manifest_path.open(encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)
        if not isinstance(manifest, dict):
            raise ValueError("Execution manifest must be a JSON object.")
        manifest.update(
            {
                "pipeline_status": PipelineStatus.FAILED.value,
                "pipeline_failure_stage": failure_stage,
                "pipeline_error_type": error_type,
            }
        )
        _write_json_atomically(batch_result.manifest_path, manifest, replace=True)
    except (OSError, ValueError):
        logger.error(
            "DevFlow pipeline failure could not be recorded in the manifest.",
            extra={
                "operation": "devflow_pipeline",
                "run_id": batch_result.run_id,
                "stage": failure_stage,
                "status": "failed",
            },
        )


def _write_json_atomically(
    destination: Path,
    document: dict[str, Any],
    *,
    replace: bool = False,
) -> None:
    """Write a JSON document beside its destination and publish it atomically."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not replace:
        raise FileExistsError(f"Pipeline output already exists: {destination}")
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(document, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


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
        raw_path=None,
        normalized_path=None,
        analytics_path=None,
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
    analytics_path: Path | None,
) -> PipelineResult:
    """Adapt a repository batch result to the public pipeline contract."""
    return PipelineResult(
        run_id=batch_result.run_id,
        started_at=started_at,
        extracted_at=extracted_at,
        status=PipelineStatus(batch_result.status),
        repositories_succeeded=batch_result.repositories_succeeded,
        repositories_failed=batch_result.repositories_failed,
        raw_path=batch_result.raw_path,
        normalized_path=batch_result.normalized_path,
        analytics_path=analytics_path,
        manifest_path=batch_result.manifest_path,
        stages=tuple(stages),
    )


def _post_batch_failed_result(
    *,
    batch_result: RepositoryBatchResult,
    started_at: datetime,
    extracted_at: datetime,
    stages: list[PipelineStageResult],
    error: Exception,
    failure_stage: str,
) -> PipelineResult:
    """Return a safe failure while preserving committed extraction outputs."""
    return PipelineResult(
        run_id=batch_result.run_id,
        started_at=started_at,
        extracted_at=extracted_at,
        status=PipelineStatus.FAILED,
        repositories_succeeded=batch_result.repositories_succeeded,
        repositories_failed=batch_result.repositories_failed,
        raw_path=batch_result.raw_path,
        normalized_path=batch_result.normalized_path,
        analytics_path=None,
        manifest_path=batch_result.manifest_path,
        stages=tuple(stages),
        error_type=type(error).__name__,
        error_message={
            "quality": "Normalized output failed quality validation.",
            "analytics": "Analytics output could not be published.",
        }[failure_stage],
    )
