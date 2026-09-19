"""BigQuery adapter for normalized GitHub repository records.

The adapter depends on a small client protocol instead of the Google SDK.
Production composition can inject ``google.cloud.bigquery.Client`` without
making the core ingestion package depend on that library.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from ingestion.common.repository_sink import RepositoryWriteResult

REPOSITORY_TABLE_SCHEMA: tuple[dict[str, str], ...] = (
    {"name": "run_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "repository_id", "type": "INTEGER", "mode": "REQUIRED"},
    {"name": "repository_name", "type": "STRING", "mode": "REQUIRED"},
    {"name": "full_name", "type": "STRING", "mode": "REQUIRED"},
    {"name": "owner_login", "type": "STRING", "mode": "REQUIRED"},
    {"name": "description", "type": "STRING", "mode": "NULLABLE"},
    {"name": "visibility", "type": "STRING", "mode": "REQUIRED"},
    {"name": "default_branch", "type": "STRING", "mode": "REQUIRED"},
    {"name": "language", "type": "STRING", "mode": "NULLABLE"},
    {"name": "is_fork", "type": "BOOLEAN", "mode": "REQUIRED"},
    {"name": "is_archived", "type": "BOOLEAN", "mode": "REQUIRED"},
    {"name": "is_disabled", "type": "BOOLEAN", "mode": "REQUIRED"},
    {"name": "created_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "updated_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "pushed_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    {"name": "stars_count", "type": "INTEGER", "mode": "REQUIRED"},
    {"name": "forks_count", "type": "INTEGER", "mode": "REQUIRED"},
    {"name": "open_issues_count", "type": "INTEGER", "mode": "REQUIRED"},
    {"name": "subscribers_count", "type": "INTEGER", "mode": "REQUIRED"},
    {"name": "size_kb", "type": "INTEGER", "mode": "REQUIRED"},
    {"name": "html_url", "type": "STRING", "mode": "REQUIRED"},
    {"name": "extracted_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
)

_SCHEMA_FIELDS = frozenset(field["name"] for field in REPOSITORY_TABLE_SCHEMA)
_TIMESTAMP_FIELDS = frozenset(
    field["name"] for field in REPOSITORY_TABLE_SCHEMA if field["type"] == "TIMESTAMP"
)


class BigQueryInsertClient(Protocol):
    """Subset of the BigQuery client needed by this adapter."""

    def insert_rows_json(
        self,
        table: str,
        json_rows: Sequence[Mapping[str, Any]],
        *,
        row_ids: Sequence[str],
    ) -> Sequence[Mapping[str, Any]]:
        """Insert JSON rows and return per-row errors."""
        ...


class BigQueryRepositoryWriteError(RuntimeError):
    """Raised when BigQuery rejects one or more repository rows."""


class BigQueryRepositorySink:
    """Write normalized repository records through a compatible client."""

    def __init__(self, client: BigQueryInsertClient, *, table: str) -> None:
        normalized_table = table.strip()
        if not normalized_table:
            raise ValueError("BigQuery table must be a non-empty identifier.")
        self._client = client
        self._table = normalized_table

    def write(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        run_id: str,
    ) -> RepositoryWriteResult:
        """Insert rows with deterministic IDs for best-effort deduplication."""
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            raise ValueError("run_id must be non-empty.")

        rows = [_prepare_row(record, run_id=normalized_run_id) for record in records]
        row_ids = [f"{normalized_run_id}:{row['repository_id']}" for row in rows]
        if len(row_ids) != len(set(row_ids)):
            raise ValueError("Repository records contain duplicate identities.")
        if not rows:
            return RepositoryWriteResult(rows_attempted=0, rows_written=0)

        try:
            errors = self._client.insert_rows_json(
                self._table,
                rows,
                row_ids=row_ids,
            )
        except Exception:
            raise BigQueryRepositoryWriteError("BigQuery insert failed.") from None
        if errors:
            raise BigQueryRepositoryWriteError(
                f"BigQuery rejected {len(errors)} repository row(s)."
            )

        return RepositoryWriteResult(
            rows_attempted=len(rows),
            rows_written=len(rows),
        )


def _prepare_row(record: Mapping[str, Any], *, run_id: str) -> dict[str, Any]:
    """Validate the storage shape and serialize timestamps as UTC RFC 3339."""
    supported_input_fields = _SCHEMA_FIELDS - {"run_id"}
    unknown_fields = set(record) - supported_input_fields
    if unknown_fields:
        raise ValueError(
            "Repository record contains unsupported fields: "
            + ", ".join(sorted(unknown_fields))
        )

    required_fields = {
        field["name"]
        for field in REPOSITORY_TABLE_SCHEMA
        if field["mode"] == "REQUIRED" and field["name"] != "run_id"
    }
    missing_fields = required_fields - set(record)
    if missing_fields:
        raise ValueError(
            "Repository record is missing required fields: "
            + ", ".join(sorted(missing_fields))
        )

    null_required_fields = {
        field_name for field_name in required_fields if record[field_name] is None
    }
    if null_required_fields:
        raise ValueError(
            "Repository record contains null required fields: "
            + ", ".join(sorted(null_required_fields))
        )

    row = {"run_id": run_id}
    for field_name in supported_input_fields:
        value = record.get(field_name)
        if field_name in _TIMESTAMP_FIELDS and value is not None:
            value = _serialize_timestamp(value, field_name=field_name)
        row[field_name] = value
    return row


def _serialize_timestamp(value: object, *, field_name: str) -> str:
    """Serialize an aware datetime to a stable UTC BigQuery timestamp value."""
    if not isinstance(value, datetime):
        raise ValueError(f"Field '{field_name}' must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"Field '{field_name}' must include timezone information.")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
