"""Acceptance tests for the normalized ingestion-to-analytics handoff."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from analytics.contracts.repository import RepositoryContract
from ingestion.github.repository_batch import (
    RepositoryBatchResult,
    _serialize_normalized_record,
)
from ingestion.github.repository_metadata import RepositoryMetadata
from orchestration.pipeline import _run_analytics


def _github_payload() -> dict[str, object]:
    return {
        "id": 1296269,
        "name": "airflow",
        "full_name": "apache/airflow",
        "owner": {"login": "apache"},
        "description": "Workflow orchestration platform",
        "visibility": "public",
        "default_branch": "main",
        "language": "Python",
        "fork": False,
        "archived": False,
        "disabled": False,
        "created_at": "2015-04-13T13:04:58Z",
        "updated_at": "2026-09-18T12:00:00Z",
        "pushed_at": "2026-09-18T11:00:00Z",
        "stargazers_count": 40000,
        "forks_count": 15000,
        "open_issues_count": 1000,
        "subscribers_count": 700,
        "size": 250000,
        "html_url": "https://github.com/apache/airflow",
    }


def test_ingestion_normalized_jsonl_runs_through_quality_and_analytics(
    tmp_path: Path,
) -> None:
    """The serialized ingestion record must satisfy the complete analytics gate."""
    extracted_at = datetime(2026, 9, 18, 12, 30, tzinfo=UTC)
    run_id = "20260918T123000000000Z"
    metadata = RepositoryMetadata.from_github_payload(
        _github_payload(),
        extracted_at=extracted_at,
    )
    normalized_record = _serialize_normalized_record(
        metadata.to_record(),
        run_id=run_id,
    )

    contract_fields = {field.name for field in RepositoryContract.get_schema().fields}
    assert set(normalized_record) == {"run_id", *contract_fields}
    contract_record = RepositoryContract.validate(normalized_record)
    assert contract_record.full_name == "apache/airflow"

    normalized_path = tmp_path / "normalized.jsonl"
    normalized_path.write_text(
        json.dumps(normalized_record) + "\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"run_id": run_id, "status": "success"}),
        encoding="utf-8",
    )
    batch_result = RepositoryBatchResult(
        run_id=run_id,
        status="success",
        repositories_succeeded=1,
        repositories_failed=0,
        output_root=tmp_path,
        raw_path=tmp_path / "raw.jsonl",
        normalized_path=normalized_path,
        manifest_path=manifest_path,
    )

    analytics_path = _run_analytics(
        batch_result=batch_result,
        extracted_at=extracted_at,
    )

    report = json.loads(analytics_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert report["quality"]["summary"]["is_valid"] is True
    assert report["meta"]["processed_records"] == 1
    assert report["repositories"][0]["full_name"] == "apache/airflow"
    assert manifest["analytics_records_written"] == 1
    assert (
        manifest["analytics_output"] == analytics_path.relative_to(tmp_path).as_posix()
    )
