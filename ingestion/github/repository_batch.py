"""Configurable repository batch extraction with atomic local persistence.

Each output file is published atomically from a temporary file in its own
directory. The three publications cannot form one cross-file transaction, so a
filesystem failure between replacements may leave an earlier output published.
The manifest is always published last and only after raw and normalized data.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Literal

from ingestion.github.exceptions import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from ingestion.github.repository_service import (
    GitHubRepositoryService,
    RepositoryExtractionError,
)

logger = logging.getLogger(__name__)

type BatchStatus = Literal["success", "partial_success", "failed"]
type Clock = Callable[[], datetime]


class RepositoryBatchConfigurationError(ValueError):
    """Raised when a repository batch configuration is invalid."""


@dataclass(frozen=True, slots=True)
class RepositorySpec:
    """One validated GitHub repository identifier."""

    owner: str
    name: str


@dataclass(frozen=True, slots=True)
class RepositoryBatchConfig:
    """Validated repository batch configuration."""

    repositories: tuple[RepositorySpec, ...]


@dataclass(frozen=True, slots=True)
class RepositoryBatchResult:
    """Summary and output locations for a completed batch run."""

    run_id: str
    status: BatchStatus
    repositories_succeeded: int
    repositories_failed: int
    output_root: Path
    manifest_path: Path


@dataclass(frozen=True, slots=True)
class _OutputPaths:
    raw: Path
    normalized: Path
    manifest: Path


def load_repository_config(path: Path) -> RepositoryBatchConfig:
    """Load and validate a repository list from a JSON file."""
    try:
        with path.open(encoding="utf-8") as config_file:
            document = json.load(config_file)
    except JSONDecodeError as exc:
        raise RepositoryBatchConfigurationError(
            f"Repository configuration contains invalid JSON at line {exc.lineno}."
        ) from exc
    except UnicodeError as exc:
        raise RepositoryBatchConfigurationError(
            "Repository configuration must be valid UTF-8."
        ) from exc
    except OSError as exc:
        raise RepositoryBatchConfigurationError(
            "Repository configuration could not be read."
        ) from exc

    if not isinstance(document, dict):
        raise RepositoryBatchConfigurationError(
            "Repository configuration root must be a JSON object."
        )

    repositories = document.get("repositories")

    if not isinstance(repositories, list) or not repositories:
        raise RepositoryBatchConfigurationError(
            "'repositories' must be a non-empty list."
        )

    validated: list[RepositorySpec] = []
    seen: set[tuple[str, str]] = set()

    for index, item in enumerate(repositories, start=1):
        if not isinstance(item, dict):
            raise RepositoryBatchConfigurationError(
                f"Repository item {index} must be a JSON object."
            )

        owner = _validate_repository_component(
            item.get("owner"),
            field_name="owner",
            item_number=index,
        )
        name = _validate_repository_component(
            item.get("name"),
            field_name="name",
            item_number=index,
        )
        identity = (owner.casefold(), name.casefold())

        if identity in seen:
            raise RepositoryBatchConfigurationError(
                f"Repository item {index} is a duplicate: {owner}/{name}."
            )

        seen.add(identity)
        validated.append(RepositorySpec(owner=owner, name=name))

    return RepositoryBatchConfig(repositories=tuple(validated))


class GitHubRepositoryBatch:
    """Extract configured repositories and persist one local batch run."""

    def __init__(
        self,
        service: GitHubRepositoryService,
        *,
        clock: Clock | None = None,
    ) -> None:
        """Initialize the batch with an extraction service and injectable clock."""
        self._service = service
        self._clock = clock or _utc_now

    def run(
        self,
        config: RepositoryBatchConfig,
        *,
        output_root: Path,
    ) -> RepositoryBatchResult:
        """Execute one repository batch and atomically publish its outputs."""
        started_at = _read_utc_clock(self._clock, field_name="started_at")
        extracted_at = _read_utc_clock(self._clock, field_name="extracted_at")
        run_id = extracted_at.strftime("%Y%m%dT%H%M%S%fZ")
        output_root = Path(output_root)
        paths = _build_output_paths(
            output_root=output_root,
            extraction_date=extracted_at.date().isoformat(),
            run_id=run_id,
        )
        _reject_existing_outputs(paths)

        raw_records: list[dict[str, Any]] = []
        normalized_records: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        for repository in config.repositories:
            try:
                result = self._service.extract_repository_with_payload(
                    repository.owner,
                    repository.name,
                    extracted_at=extracted_at,
                )
                raw_record = {
                    "run_id": run_id,
                    "extracted_at": extracted_at.isoformat(),
                    "owner": repository.owner,
                    "repository": repository.name,
                    "endpoint": result.endpoint,
                    "payload": result.payload,
                }
                normalized_record = _serialize_normalized_record(
                    result.metadata.to_record(),
                    run_id=run_id,
                )
            except Exception as exc:
                error = _safe_repository_error(repository, exc)
                errors.append(error)
                logger.error(
                    "GitHub repository batch item failed.",
                    extra={
                        "operation": "github_repository_batch_item",
                        "owner": repository.owner,
                        "repository": repository.name,
                        "error_type": error["error_type"],
                    },
                )
                continue

            raw_records.append(raw_record)
            normalized_records.append(normalized_record)

        succeeded = len(raw_records)
        failed = len(errors)
        status = _batch_status(succeeded=succeeded, failed=failed)
        manifest_fields = {
            "run_id": run_id,
            "started_at": started_at.isoformat(),
            "extracted_at": extracted_at.isoformat(),
            "status": status,
            "repositories_requested": len(config.repositories),
            "repositories_succeeded": succeeded,
            "repositories_failed": failed,
            "raw_output": paths.raw.relative_to(output_root).as_posix(),
            "normalized_output": paths.normalized.relative_to(output_root).as_posix(),
            "errors": errors,
        }

        _publish_outputs_atomically(
            paths=paths,
            raw_records=raw_records,
            normalized_records=normalized_records,
            manifest_fields=manifest_fields,
            run_id=run_id,
            clock=self._clock,
        )

        return RepositoryBatchResult(
            run_id=run_id,
            status=status,
            repositories_succeeded=succeeded,
            repositories_failed=failed,
            output_root=output_root,
            manifest_path=paths.manifest,
        )


def _validate_repository_component(
    value: object,
    *,
    field_name: str,
    item_number: int,
) -> str:
    """Validate one owner or repository name from configuration."""
    if not isinstance(value, str) or not value.strip():
        raise RepositoryBatchConfigurationError(
            f"Repository item {item_number} field '{field_name}' "
            "must be a non-empty string."
        )

    normalized = value.strip()

    if "/" in normalized or "\\" in normalized:
        raise RepositoryBatchConfigurationError(
            f"Repository item {item_number} field '{field_name}' "
            "cannot contain a path separator."
        )

    return normalized


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(UTC)


def _read_utc_clock(clock: Clock, *, field_name: str) -> datetime:
    """Read and normalize one timezone-aware value from the batch clock."""
    value = clock()

    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} clock value must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} clock value must include timezone information.")

    return value.astimezone(UTC)


def _build_output_paths(
    *,
    output_root: Path,
    extraction_date: str,
    run_id: str,
) -> _OutputPaths:
    """Build final locations for all outputs in one run."""
    partition = Path(f"extraction_date={extraction_date}") / f"run_id={run_id}"
    return _OutputPaths(
        raw=output_root
        / "raw"
        / "github"
        / "repositories"
        / partition
        / "repositories.jsonl",
        normalized=output_root
        / "normalized"
        / "github"
        / "repositories"
        / partition
        / "repositories.jsonl",
        manifest=output_root
        / "manifests"
        / "github"
        / "repositories"
        / partition
        / "manifest.json",
    )


def _reject_existing_outputs(paths: _OutputPaths) -> None:
    """Reject a run identifier whose final output already exists."""
    existing = [
        path for path in (paths.raw, paths.normalized, paths.manifest) if path.exists()
    ]

    if existing:
        raise FileExistsError(f"Batch output already exists: {existing[0]}")


def _safe_repository_error(
    repository: RepositorySpec,
    error: Exception,
) -> dict[str, str]:
    """Build a manifest error without copying potentially sensitive content."""
    if isinstance(error, GitHubAuthenticationError):
        error_type = type(error).__name__
        message = "GitHub authentication failed."
    elif isinstance(error, GitHubNotFoundError):
        error_type = type(error).__name__
        message = "GitHub repository was not found."
    elif isinstance(error, GitHubRateLimitError):
        error_type = type(error).__name__
        message = "GitHub API rate limit reached."
    elif isinstance(error, RepositoryExtractionError):
        error_type = type(error).__name__
        message = "GitHub repository response could not be normalized."
    elif isinstance(error, GitHubAPIError):
        error_type = type(error).__name__
        message = "GitHub API request failed."
    else:
        error_type = "UnexpectedRepositoryError"
        message = "Unexpected repository extraction error."

    return {
        "owner": repository.owner,
        "repository": repository.name,
        "error_type": error_type,
        "message": message,
    }


def _serialize_normalized_record(
    record: Mapping[str, Any],
    *,
    run_id: str,
) -> dict[str, Any]:
    """Copy a normalized record and convert its datetimes to UTC strings."""
    serialized: dict[str, Any] = {"run_id": run_id}

    for key, value in record.items():
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(
                    f"Normalized datetime field '{key}' must include "
                    "timezone information."
                )
            serialized[key] = value.astimezone(UTC).isoformat()
        else:
            serialized[key] = value

    return serialized


def _batch_status(*, succeeded: int, failed: int) -> BatchStatus:
    """Determine the final status from repository counters."""
    if succeeded and failed:
        return "partial_success"
    if succeeded:
        return "success"
    return "failed"


def _publish_outputs_atomically(
    *,
    paths: _OutputPaths,
    raw_records: Sequence[Mapping[str, Any]],
    normalized_records: Sequence[Mapping[str, Any]],
    manifest_fields: Mapping[str, Any],
    run_id: str,
    clock: Clock,
) -> None:
    """Publish raw and normalized, then timestamp and publish the manifest.

    Raw and normalized are written to local temporaries and published first.
    The completion time is then read before the manifest is written and
    published last.
    """
    temporary_paths: list[Path] = []

    try:
        raw_temporary = _create_temporary_path(
            destination=paths.raw,
            run_id=run_id,
        )
        temporary_paths.append(raw_temporary)
        normalized_temporary = _create_temporary_path(
            destination=paths.normalized,
            run_id=run_id,
        )
        temporary_paths.append(normalized_temporary)
        manifest_temporary = _create_temporary_path(
            destination=paths.manifest,
            run_id=run_id,
        )
        temporary_paths.append(manifest_temporary)

        _reject_existing_outputs(paths)
        _write_json_lines_temporary(raw_temporary, raw_records)
        _write_json_lines_temporary(normalized_temporary, normalized_records)
        os.replace(raw_temporary, paths.raw)
        os.replace(normalized_temporary, paths.normalized)

        completed_at = _read_utc_clock(clock, field_name="completed_at")
        manifest = {
            **manifest_fields,
            "completed_at": completed_at.isoformat(),
        }
        _write_json_temporary(manifest_temporary, manifest)
        os.replace(manifest_temporary, paths.manifest)
    finally:
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)


def _create_temporary_path(
    *,
    destination: Path,
    run_id: str,
) -> Path:
    """Create and close one tracked temporary beside its destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.{run_id}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(file_descriptor)
    return Path(temporary_name)


def _write_json_lines_temporary(
    temporary_path: Path,
    records: Sequence[Mapping[str, Any]],
) -> None:
    """Write and close one complete JSON Lines temporary."""
    with temporary_path.open(
        mode="w", encoding="utf-8", newline="\n"
    ) as temporary_file:
        for record in records:
            temporary_file.write(json.dumps(record, ensure_ascii=False))
            temporary_file.write("\n")


def _write_json_temporary(
    temporary_path: Path,
    document: Mapping[str, Any],
) -> None:
    """Write and close one complete JSON document temporary."""
    with temporary_path.open(
        mode="w", encoding="utf-8", newline="\n"
    ) as temporary_file:
        json.dump(document, temporary_file, ensure_ascii=False, indent=2)
        temporary_file.write("\n")
