"""Tests for the dependency-free BigQuery repository sink."""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from ingestion.bigquery.repository_sink import (
    REPOSITORY_TABLE_SCHEMA,
    BigQueryInsertClient,
    BigQueryRepositorySink,
    BigQueryRepositoryWriteError,
)


def build_record() -> dict[str, object]:
    """Build one normalized repository record."""
    return {
        "repository_id": 1296269,
        "repository_name": "airflow",
        "full_name": "apache/airflow",
        "owner_login": "apache",
        "description": None,
        "visibility": "public",
        "default_branch": "main",
        "language": "Python",
        "is_fork": False,
        "is_archived": False,
        "is_disabled": False,
        "created_at": datetime(
            2015,
            4,
            13,
            13,
            4,
            58,
            tzinfo=timezone(timedelta(hours=-5)),
        ),
        "updated_at": datetime(2026, 7, 22, 20, 0, tzinfo=UTC),
        "pushed_at": None,
        "stars_count": 40000,
        "forks_count": 15000,
        "open_issues_count": 1000,
        "subscribers_count": 700,
        "size_kb": 250000,
        "html_url": "https://github.com/apache/airflow",
        "extracted_at": datetime(2026, 7, 22, 22, 0, tzinfo=UTC),
    }


def test_schema_matches_normalized_repository_contract() -> None:
    """The public schema must remain explicit and complete."""
    fields = {field["name"]: field for field in REPOSITORY_TABLE_SCHEMA}

    assert set(fields) == {"run_id", *build_record()}
    assert fields["repository_id"] == {
        "name": "repository_id",
        "type": "INTEGER",
        "mode": "REQUIRED",
    }
    assert fields["pushed_at"]["mode"] == "NULLABLE"
    assert fields["extracted_at"]["type"] == "TIMESTAMP"


def test_write_uses_utc_timestamps_and_deterministic_row_ids() -> None:
    """Rows must be BigQuery-ready and retry with the same insertion identity."""
    client = Mock(spec=BigQueryInsertClient)
    client.insert_rows_json.return_value = []
    sink = BigQueryRepositorySink(client, table="project.dataset.repositories")

    result = sink.write([build_record()], run_id="run-123")

    assert result.rows_attempted == 1
    assert result.rows_written == 1
    table, rows = client.insert_rows_json.call_args.args
    assert table == "project.dataset.repositories"
    assert rows[0]["run_id"] == "run-123"
    assert rows[0]["created_at"] == "2015-04-13T18:04:58Z"
    assert rows[0]["extracted_at"] == "2026-07-22T22:00:00Z"
    assert client.insert_rows_json.call_args.kwargs["row_ids"] == ["run-123:1296269"]


def test_write_rejects_naive_datetime_before_client_call() -> None:
    """Naive timestamps must never reach BigQuery with ambiguous semantics."""
    client = Mock(spec=BigQueryInsertClient)
    record = build_record()
    record["updated_at"] = datetime(2026, 7, 22, 20, 0)

    with pytest.raises(ValueError, match="updated_at.*timezone"):
        BigQueryRepositorySink(client, table="project.dataset.repositories").write(
            [record],
            run_id="run-123",
        )

    client.insert_rows_json.assert_not_called()


def test_write_rejects_duplicate_repository_identity() -> None:
    """One run cannot submit duplicate insertion IDs."""
    client = Mock(spec=BigQueryInsertClient)
    record = build_record()

    with pytest.raises(ValueError, match="duplicate identities"):
        BigQueryRepositorySink(client, table="project.dataset.repositories").write(
            [record, record.copy()],
            run_id="run-123",
        )

    client.insert_rows_json.assert_not_called()


def test_write_raises_sanitized_error_when_bigquery_rejects_rows() -> None:
    """Provider error bodies must not be copied into application exceptions."""
    client = Mock(spec=BigQueryInsertClient)
    client.insert_rows_json.return_value = [
        {"index": 0, "errors": [{"message": "Authorization: simulated-secret"}]}
    ]

    with pytest.raises(BigQueryRepositoryWriteError) as exception_info:
        BigQueryRepositorySink(client, table="project.dataset.repositories").write(
            [build_record()],
            run_id="run-123",
        )

    message = str(exception_info.value)
    assert "simulated-secret" not in message
    assert "Authorization" not in message


def test_empty_batch_does_not_call_client() -> None:
    """An empty batch is a successful no-op."""
    client = Mock(spec=BigQueryInsertClient)

    result = BigQueryRepositorySink(
        client,
        table="project.dataset.repositories",
    ).write([], run_id="run-123")

    assert result.rows_attempted == 0
    assert result.rows_written == 0
    client.insert_rows_json.assert_not_called()
