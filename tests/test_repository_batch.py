"""Tests for configurable repository batch extraction and local persistence."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from ingestion.github.exceptions import GitHubNotFoundError
from ingestion.github.repository_batch import (
    GitHubRepositoryBatch,
    RepositoryBatchConfigurationError,
    load_repository_config,
)
from ingestion.github.repository_metadata import RepositoryMetadata
from ingestion.github.repository_service import (
    GitHubRepositoryService,
    RepositoryExtractionResult,
)


def build_payload(
    *,
    owner: str = "apache",
    repository: str = "airflow",
    repository_id: int = 1,
) -> dict[str, object]:
    """Build one representative GitHub repository payload."""
    return {
        "id": repository_id,
        "name": repository,
        "full_name": f"{owner}/{repository}",
        "owner": {"login": owner},
        "description": "Example repository",
        "visibility": "public",
        "default_branch": "main",
        "language": "Python",
        "fork": False,
        "archived": False,
        "disabled": False,
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2026-07-23T12:00:00Z",
        "pushed_at": "2026-07-23T11:00:00Z",
        "stargazers_count": 10,
        "forks_count": 2,
        "open_issues_count": 1,
        "subscribers_count": 3,
        "size": 100,
        "html_url": f"https://github.com/{owner}/{repository}",
        "custom_source_field": {"preserved": True},
    }


def build_result(
    extracted_at: datetime,
    *,
    owner: str = "apache",
    repository: str = "airflow",
    repository_id: int = 1,
) -> RepositoryExtractionResult:
    """Build one service result with its untouched source payload."""
    payload = build_payload(
        owner=owner,
        repository=repository,
        repository_id=repository_id,
    )
    return RepositoryExtractionResult(
        endpoint=f"/repos/{owner}/{repository}",
        payload=payload,
        metadata=RepositoryMetadata.from_github_payload(
            payload,
            extracted_at=extracted_at,
        ),
    )


def write_config(path: Path, repositories: object) -> None:
    """Write a JSON configuration fixture."""
    path.write_text(
        json.dumps({"repositories": repositories}),
        encoding="utf-8",
    )


def sequence_clock(values: list[datetime]):
    """Return a deterministic clock over the provided values."""
    iterator: Iterator[datetime] = iter(values)
    return lambda: next(iterator)


def test_load_repository_config_accepts_multiple_repositories(tmp_path: Path) -> None:
    """A valid configuration must preserve every requested repository."""
    config_path = tmp_path / "repositories.json"
    write_config(
        config_path,
        [
            {"owner": "apache", "name": "airflow"},
            {"owner": "pandas-dev", "name": "pandas"},
        ],
    )

    config = load_repository_config(config_path)

    assert [(item.owner, item.name) for item in config.repositories] == [
        ("apache", "airflow"),
        ("pandas-dev", "pandas"),
    ]


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ([], "root.*object"),
        ({}, "repositories"),
        ({"repositories": []}, "non-empty list"),
        ({"repositories": ["apache/airflow"]}, "item 1.*object"),
        ({"repositories": [{"name": "airflow"}]}, "owner"),
        ({"repositories": [{"owner": "apache", "name": ""}]}, "name"),
        ({"repositories": [{"owner": "apache/team", "name": "airflow"}]}, "separator"),
    ],
)
def test_load_repository_config_rejects_invalid_documents(
    tmp_path: Path,
    document: object,
    message: str,
) -> None:
    """Invalid configuration shapes must produce clear validation errors."""
    config_path = tmp_path / "repositories.json"
    config_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RepositoryBatchConfigurationError, match=message):
        load_repository_config(config_path)


def test_load_repository_config_rejects_case_insensitive_duplicates(
    tmp_path: Path,
) -> None:
    """GitHub repository identifiers must be unique regardless of case."""
    config_path = tmp_path / "repositories.json"
    write_config(
        config_path,
        [
            {"owner": "Apache", "name": "Airflow"},
            {"owner": "apache", "name": "airflow"},
        ],
    )

    with pytest.raises(RepositoryBatchConfigurationError, match="duplicate"):
        load_repository_config(config_path)


def test_load_repository_config_wraps_read_errors(tmp_path: Path) -> None:
    """Unreadable configuration must produce a safe configuration error."""
    missing_path = tmp_path / "missing.json"

    with pytest.raises(
        RepositoryBatchConfigurationError,
        match="could not be read",
    ) as exception_info:
        load_repository_config(missing_path)

    assert isinstance(exception_info.value.__cause__, OSError)


def test_load_repository_config_rejects_invalid_utf8(tmp_path: Path) -> None:
    """Configuration bytes must contain valid UTF-8 without leaking content."""
    config_path = tmp_path / "invalid-utf8.json"
    config_path.write_bytes(b'\xff\xfe{"binary-content": "must-not-leak"}')

    with pytest.raises(
        RepositoryBatchConfigurationError,
        match="valid UTF-8",
    ) as exception_info:
        load_repository_config(config_path)

    assert isinstance(exception_info.value.__cause__, UnicodeError)


def test_batch_persists_raw_normalized_and_manifest_with_shared_timestamp(
    tmp_path: Path,
) -> None:
    """Successful records must share one timestamp and preserve source data."""
    started_at = datetime(2026, 7, 23, 12, 0, 0, tzinfo=UTC)
    extracted_at = datetime(2026, 7, 23, 12, 0, 1, 123456, tzinfo=UTC)
    completed_at = datetime(2026, 7, 23, 12, 0, 5, tzinfo=UTC)

    config_path = tmp_path / "repositories.json"
    write_config(
        config_path,
        [
            {"owner": "apache", "name": "airflow"},
            {"owner": "pandas-dev", "name": "pandas"},
        ],
    )
    config = load_repository_config(config_path)

    service = Mock(spec=GitHubRepositoryService)
    service.extract_repository_with_payload.side_effect = [
        build_result(extracted_at),
        build_result(
            extracted_at,
            owner="pandas-dev",
            repository="pandas",
            repository_id=2,
        ),
    ]
    batch = GitHubRepositoryBatch(
        service,
        clock=sequence_clock([started_at, extracted_at, completed_at]),
    )

    result = batch.run(config, output_root=tmp_path / "data")

    assert result.status == "success"
    assert result.run_id == "20260723T120001123456Z"
    assert result.manifest_path.exists()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["started_at"] == started_at.isoformat()
    assert manifest["extracted_at"] == extracted_at.isoformat()
    assert manifest["completed_at"] == completed_at.isoformat()
    assert manifest["repositories_requested"] == 2
    assert manifest["repositories_succeeded"] == 2
    assert manifest["repositories_failed"] == 0
    assert manifest["raw_output"].startswith("raw/")
    assert manifest["normalized_output"].startswith("normalized/")
    assert "\\" not in manifest["raw_output"]

    raw_path = result.output_root / manifest["raw_output"]
    normalized_path = result.output_root / manifest["normalized_output"]
    raw_records = [
        json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()
    ]
    normalized_records = [
        json.loads(line)
        for line in normalized_path.read_text(encoding="utf-8").splitlines()
    ]

    assert len(raw_records) == len(normalized_records) == 2
    assert raw_records[0]["payload"] == build_payload()
    assert raw_records[0]["run_id"] == result.run_id
    assert raw_records[0]["extracted_at"] == extracted_at.isoformat()
    assert normalized_records[0]["run_id"] == result.run_id
    assert normalized_records[0]["created_at"] == "2020-01-01T00:00:00+00:00"
    assert normalized_records[0]["extracted_at"] == extracted_at.isoformat()

    for call in service.extract_repository_with_payload.call_args_list:
        assert call.kwargs["extracted_at"] == extracted_at


def test_batch_continues_after_failure_and_reports_partial_success(
    tmp_path: Path,
) -> None:
    """One repository failure must not stop subsequent repositories."""
    times = [datetime(2026, 7, 23, 13, 0, second, tzinfo=UTC) for second in (0, 1, 2)]
    config_path = tmp_path / "repositories.json"
    write_config(
        config_path,
        [
            {"owner": "missing", "name": "repository"},
            {"owner": "apache", "name": "airflow"},
        ],
    )
    config = load_repository_config(config_path)
    service = Mock(spec=GitHubRepositoryService)
    service.extract_repository_with_payload.side_effect = [
        GitHubNotFoundError("sensitive source response"),
        build_result(times[1]),
    ]

    result = GitHubRepositoryBatch(
        service,
        clock=sequence_clock(times),
    ).run(config, output_root=tmp_path / "data")

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert result.status == "partial_success"
    assert manifest["repositories_succeeded"] == 1
    assert manifest["repositories_failed"] == 1
    assert manifest["errors"] == [
        {
            "owner": "missing",
            "repository": "repository",
            "error_type": "GitHubNotFoundError",
            "message": "GitHub repository was not found.",
        }
    ]
    assert service.extract_repository_with_payload.call_count == 2


def test_batch_continues_without_orphan_raw_after_serialization_failure(
    tmp_path: Path,
) -> None:
    """Raw and normalized records must be committed per repository as one unit."""
    times = [datetime(2026, 7, 23, 13, 30, second, tzinfo=UTC) for second in (0, 1, 2)]
    config_path = tmp_path / "repositories.json"
    write_config(
        config_path,
        [
            {"owner": "broken", "name": "repository"},
            {"owner": "apache", "name": "airflow"},
        ],
    )
    config = load_repository_config(config_path)
    broken_metadata = Mock(spec=RepositoryMetadata)
    broken_metadata.to_record.side_effect = ValueError(
        "Authorization: Bearer simulated-token"
    )
    service = Mock(spec=GitHubRepositoryService)
    service.extract_repository_with_payload.side_effect = [
        RepositoryExtractionResult(
            endpoint="/repos/broken/repository",
            payload={"id": "raw-must-not-be-written"},
            metadata=broken_metadata,
        ),
        build_result(times[1]),
    ]

    result = GitHubRepositoryBatch(
        service,
        clock=sequence_clock(times),
    ).run(config, output_root=tmp_path / "data")

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    raw_path = result.output_root / manifest["raw_output"]
    normalized_path = result.output_root / manifest["normalized_output"]
    raw_records = [
        json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()
    ]
    normalized_records = [
        json.loads(line)
        for line in normalized_path.read_text(encoding="utf-8").splitlines()
    ]

    assert result.status == "partial_success"
    assert service.extract_repository_with_payload.call_count == 2
    assert len(raw_records) == len(normalized_records) == 1
    assert raw_records[0]["owner"] == "apache"
    assert normalized_records[0]["owner_login"] == "apache"
    assert manifest["repositories_succeeded"] == 1
    assert manifest["repositories_failed"] == 1
    assert manifest["errors"][0] == {
        "owner": "broken",
        "repository": "repository",
        "error_type": "UnexpectedRepositoryError",
        "message": "Unexpected repository extraction error.",
    }
    assert "simulated-token" not in result.manifest_path.read_text(encoding="utf-8")


def test_batch_reports_failed_when_every_repository_fails(tmp_path: Path) -> None:
    """A run without successful repositories must be marked failed."""
    times = [datetime(2026, 7, 23, 14, 0, second, tzinfo=UTC) for second in (0, 1, 2)]
    config_path = tmp_path / "repositories.json"
    write_config(config_path, [{"owner": "missing", "name": "one"}])
    config = load_repository_config(config_path)
    service = Mock(spec=GitHubRepositoryService)
    service.extract_repository_with_payload.side_effect = GitHubNotFoundError(
        "not found"
    )

    result = GitHubRepositoryBatch(
        service,
        clock=sequence_clock(times),
    ).run(config, output_root=tmp_path / "data")

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert result.status == "failed"
    assert manifest["repositories_succeeded"] == 0
    assert manifest["repositories_failed"] == 1


def test_unexpected_repository_error_does_not_persist_secrets(tmp_path: Path) -> None:
    """Unexpected exception content must never be copied to the manifest."""
    secret = "Authorization: Bearer simulated-token"
    times = [datetime(2026, 7, 23, 15, 0, second, tzinfo=UTC) for second in (0, 1, 2)]
    config_path = tmp_path / "repositories.json"
    write_config(config_path, [{"owner": "apache", "name": "airflow"}])
    config = load_repository_config(config_path)
    service = Mock(spec=GitHubRepositoryService)
    service.extract_repository_with_payload.side_effect = RuntimeError(secret)

    result = GitHubRepositoryBatch(
        service,
        clock=sequence_clock(times),
    ).run(config, output_root=tmp_path / "data")

    manifest_text = result.manifest_path.read_text(encoding="utf-8")
    assert "Authorization" not in manifest_text
    assert "simulated-token" not in manifest_text
    persisted_error = json.loads(manifest_text)["errors"][0]
    assert persisted_error["error_type"] == "UnexpectedRepositoryError"
    assert persisted_error["message"] == "Unexpected repository extraction error."


def test_atomic_writer_publishes_manifest_last_and_uses_local_temporaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All local temporaries must close before outputs are published in order."""
    times = [datetime(2026, 7, 23, 16, 0, second, tzinfo=UTC) for second in (0, 1, 2)]
    config_path = tmp_path / "repositories.json"
    write_config(config_path, [{"owner": "apache", "name": "airflow"}])
    config = load_repository_config(config_path)
    service = Mock(spec=GitHubRepositoryService)
    service.extract_repository_with_payload.return_value = build_result(times[1])
    replacements: list[tuple[Path, Path]] = []
    events: list[str] = []
    real_replace = os.replace
    clock_values: Iterator[datetime] = iter(times)
    clock_reads = 0

    def event_clock() -> datetime:
        nonlocal clock_reads
        clock_reads += 1
        if clock_reads == 3:
            events.append("completed_at")
        return next(clock_values)

    def recording_replace(source: str | Path, destination: str | Path) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        assert source_path.parent == destination_path.parent
        replacements.append((source_path, destination_path))
        events.append(destination_path.parts[-6])
        real_replace(source_path, destination_path)

    monkeypatch.setattr(
        "ingestion.github.repository_batch.os.replace", recording_replace
    )

    result = GitHubRepositoryBatch(
        service,
        clock=event_clock,
    ).run(config, output_root=tmp_path / "data")

    assert events == ["raw", "normalized", "completed_at", "manifests"]
    assert [destination.parts[-6] for _, destination in replacements] == [
        "raw",
        "normalized",
        "manifests",
    ]
    assert replacements[-1][1] == result.manifest_path
    assert not list(result.output_root.rglob("*.tmp"))


def test_atomic_writer_rejects_existing_run_outputs(tmp_path: Path) -> None:
    """A repeated run identifier must never overwrite prior final files."""
    times = [datetime(2026, 7, 23, 17, 0, second, tzinfo=UTC) for second in (0, 1, 2)]
    config_path = tmp_path / "repositories.json"
    write_config(config_path, [{"owner": "apache", "name": "airflow"}])
    config = load_repository_config(config_path)
    service = Mock(spec=GitHubRepositoryService)
    service.extract_repository_with_payload.return_value = build_result(times[1])

    GitHubRepositoryBatch(
        service,
        clock=sequence_clock(times),
    ).run(config, output_root=tmp_path / "data")

    repeated_clock = sequence_clock(times[:2])
    with pytest.raises(FileExistsError, match="already exists"):
        GitHubRepositoryBatch(service, clock=repeated_clock).run(
            config,
            output_root=tmp_path / "data",
        )


def test_atomic_writer_cleans_only_remaining_temporaries_on_publish_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A publication failure must remove run temporaries without deleting finals."""
    times = [datetime(2026, 7, 23, 18, 0, second, tzinfo=UTC) for second in (0, 1, 2)]
    config_path = tmp_path / "repositories.json"
    write_config(config_path, [{"owner": "apache", "name": "airflow"}])
    config = load_repository_config(config_path)
    service = Mock(spec=GitHubRepositoryService)
    service.extract_repository_with_payload.return_value = build_result(times[1])
    real_replace = os.replace
    replacement_count = 0

    def failing_replace(source: str | Path, destination: str | Path) -> None:
        nonlocal replacement_count
        replacement_count += 1
        if replacement_count == 2:
            raise OSError("simulated publication failure")
        real_replace(source, destination)

    monkeypatch.setattr("ingestion.github.repository_batch.os.replace", failing_replace)

    with pytest.raises(OSError, match="publication failure"):
        GitHubRepositoryBatch(
            service,
            clock=sequence_clock(times),
        ).run(config, output_root=tmp_path / "data")

    output_root = tmp_path / "data"
    assert len(list(output_root.rglob("repositories.jsonl"))) == 1
    assert not list(output_root.rglob("manifest.json"))
    assert not list(output_root.rglob("*.tmp"))
