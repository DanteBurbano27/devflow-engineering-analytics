"""Unit and contract tests for the repository data contract."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from analytics.contracts.repository import (
    ContractValidationError,
    RepositoryContract,
    RepositoryRecord,
)
from ingestion.github.repository_metadata import RepositoryMetadata


def make_valid_payload(**overrides: Any) -> dict[str, Any]:
    """Helper creating a baseline valid repository dictionary."""
    base: dict[str, Any] = {
        "repository_id": 1296269,
        "repository_name": "Hello-World",
        "full_name": "octocat/Hello-World",
        "owner_login": "octocat",
        "description": "Example repository",
        "visibility": "public",
        "default_branch": "main",
        "language": "Python",
        "is_fork": False,
        "is_archived": False,
        "is_disabled": False,
        "created_at": "2011-01-26T19:01:12Z",
        "updated_at": "2011-01-26T19:14:43Z",
        "pushed_at": "2011-01-26T19:06:43Z",
        "stars_count": 80,
        "forks_count": 9,
        "open_issues_count": 2,
        "subscribers_count": 42,
        "size_kb": 108,
        "html_url": "https://github.com/octocat/Hello-World",
        "extracted_at": "2026-07-22T21:45:00Z",
    }
    base.update(overrides)
    return base


def test_contract_schema_metadata() -> None:
    """The contract schema must provide valid introspection."""
    schema = RepositoryContract.get_schema()
    assert schema.name == "repository_metadata_contract"
    assert schema.version == "1.0.0"
    assert "repository_id" in schema.primary_key
    assert "full_name" in schema.primary_key

    schema_dict = schema.to_dict()
    assert schema_dict["version"] == "1.0.0"
    assert len(schema_dict["fields"]) == len(schema.fields)


def test_contract_validates_valid_dict() -> None:
    """A valid dictionary payload must produce a RepositoryRecord."""
    payload = make_valid_payload()
    record = RepositoryContract.validate(payload)

    assert isinstance(record, RepositoryRecord)
    assert record.repository_id == 1296269
    assert record.full_name == "octocat/Hello-World"
    assert record.owner_login == "octocat"
    assert record.visibility == "public"
    assert record.created_at == datetime(2011, 1, 26, 19, 1, 12, tzinfo=UTC)
    assert record.pushed_at == datetime(2011, 1, 26, 19, 6, 43, tzinfo=UTC)
    assert record.extracted_at == datetime(2026, 7, 22, 21, 45, 0, tzinfo=UTC)


def test_contract_validates_repository_metadata_instance() -> None:
    """A RepositoryMetadata instance from ingestion must be validated correctly."""
    metadata = RepositoryMetadata(
        repository_id=999,
        repository_name="core-lib",
        full_name="acme/core-lib",
        owner_login="acme",
        description=None,
        visibility="private",
        default_branch="master",
        language=None,
        is_fork=True,
        is_archived=False,
        is_disabled=False,
        created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC),
        pushed_at=None,
        stars_count=0,
        forks_count=0,
        open_issues_count=0,
        subscribers_count=1,
        size_kb=0,
        html_url="https://github.com/acme/core-lib",
        extracted_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
    )

    record = RepositoryContract.validate(metadata)
    assert record.repository_id == 999
    assert record.is_fork is True
    assert record.pushed_at is None
    assert record.language is None


def test_contract_idempotent_on_repository_record() -> None:
    """Validating an existing RepositoryRecord should return it directly."""
    payload = make_valid_payload()
    record1 = RepositoryContract.validate(payload)
    record2 = RepositoryContract.validate(record1)
    assert record1 is record2


def test_contract_fails_on_invalid_repository_id() -> None:
    """Negative, zero, or non-int repository_id must raise ContractValidationError."""
    with pytest.raises(ContractValidationError) as exc_info:
        RepositoryContract.validate(make_valid_payload(repository_id=-10))
    assert "positive integer" in str(exc_info.value)

    with pytest.raises(ContractValidationError):
        RepositoryContract.validate(make_valid_payload(repository_id=0))

    with pytest.raises(ContractValidationError):
        RepositoryContract.validate(make_valid_payload(repository_id="12345"))

    with pytest.raises(ContractValidationError):
        RepositoryContract.validate(make_valid_payload(repository_id=True))


def test_contract_fails_on_empty_strings() -> None:
    """Empty repository_name, full_name, or owner_login must be rejected."""
    with pytest.raises(ContractValidationError):
        RepositoryContract.validate(make_valid_payload(repository_name="   "))

    with pytest.raises(ContractValidationError):
        RepositoryContract.validate(make_valid_payload(full_name=""))

    with pytest.raises(ContractValidationError):
        RepositoryContract.validate(make_valid_payload(owner_login="  "))


def test_contract_fails_on_full_name_pattern_or_owner_mismatch() -> None:
    """full_name must contain '/' and match owner_login prefix."""
    with pytest.raises(ContractValidationError) as exc:
        RepositoryContract.validate(make_valid_payload(full_name="Hello-World"))
    assert "owner/repo" in str(exc.value)

    with pytest.raises(ContractValidationError) as exc2:
        RepositoryContract.validate(
            make_valid_payload(
                owner_login="octocat",
                full_name="different-org/Hello-World",
            )
        )
    assert "Inconsistent identity" in str(exc2.value)


def test_contract_fails_on_invalid_visibility() -> None:
    """Visibility outside public/private/internal must be rejected."""
    with pytest.raises(ContractValidationError) as exc:
        RepositoryContract.validate(make_valid_payload(visibility="restricted"))
    assert "Field 'visibility' must be one of" in str(exc.value)


@pytest.mark.parametrize(
    "metric_key",
    ["stars_count", "forks_count", "open_issues_count", "subscribers_count", "size_kb"],
)
def test_contract_fails_on_negative_metrics(metric_key: str) -> None:
    """Negative metric counts must raise ContractValidationError."""
    with pytest.raises(ContractValidationError) as exc:
        RepositoryContract.validate(make_valid_payload(**{metric_key: -1}))
    assert f"Field '{metric_key}' cannot be negative" in str(exc.value)


def test_contract_fails_on_unsupported_type() -> None:
    """Passing unsupported types raises ContractValidationError."""
    with pytest.raises(ContractValidationError) as exc:
        RepositoryContract.validate([1, 2, 3])  # type: ignore[arg-type]
    assert "Unsupported record type" in str(exc.value)


def test_contract_serialization() -> None:
    """RepositoryRecord.to_dict() must produce valid serializable dictionary."""
    record = RepositoryContract.validate(make_valid_payload())
    record_dict = record.to_dict()

    assert record_dict["repository_id"] == 1296269
    assert isinstance(record_dict["created_at"], str)
    assert record_dict["created_at"].startswith("2011-01-26")
    assert record_dict["extracted_at"].startswith("2026-07-22")


def test_contract_all_21_fields_presence() -> None:
    """Validate that all 21 fields defined in schema are present and populated."""
    schema = RepositoryContract.get_schema()
    assert len(schema.fields) == 21

    record = RepositoryContract.validate(make_valid_payload())
    record_dict = record.to_dict()

    field_names = {f.name for f in schema.fields}
    assert set(record_dict.keys()) == field_names
    for field in schema.fields:
        val = getattr(record, field.name)
        if not field.nullable:
            assert val is not None, f"Non-nullable field {field.name} is None"


def test_contract_nullable_fields() -> None:
    """Nullable fields (description, language, pushed_at) accept None."""
    payload = make_valid_payload(description=None, language=None, pushed_at=None)
    record = RepositoryContract.validate(payload)
    assert record.description is None
    assert record.language is None
    assert record.pushed_at is None


def test_contract_fails_on_invalid_string_types() -> None:
    """Non-string description or language must raise ContractValidationError."""
    with pytest.raises(ContractValidationError) as exc:
        RepositoryContract.validate(make_valid_payload(description=12345))
    assert "Field 'description' must be a string or null" in str(exc.value)

    with pytest.raises(ContractValidationError) as exc2:
        RepositoryContract.validate(make_valid_payload(language=True))
    assert "Field 'language' must be a string or null" in str(exc2.value)


@pytest.mark.parametrize("bool_field", ["is_fork", "is_archived", "is_disabled"])
def test_contract_fails_on_invalid_boolean_types(bool_field: str) -> None:
    """Non-bool values in boolean flags must raise ContractValidationError."""
    with pytest.raises(ContractValidationError) as exc:
        RepositoryContract.validate(make_valid_payload(**{bool_field: "true"}))
    assert f"Field '{bool_field}' must be a boolean" in str(exc.value)

    with pytest.raises(ContractValidationError):
        RepositoryContract.validate(make_valid_payload(**{bool_field: 1}))


def test_contract_fails_on_invalid_timestamps() -> None:
    """Invalid or unparseable timestamps must raise ContractValidationError."""
    with pytest.raises(ContractValidationError) as exc:
        RepositoryContract.validate(make_valid_payload(created_at="not-a-date"))
    assert "Field 'created_at' contains an invalid datetime string" in str(exc.value)

    with pytest.raises(ContractValidationError):
        RepositoryContract.validate(make_valid_payload(pushed_at="invalid-time"))


def test_contract_rejects_naive_datetimes() -> None:
    """Naive datetimes without timezone offset must be rejected."""
    naive_dt = datetime(2024, 6, 1, 12, 0, 0)
    with pytest.raises(ContractValidationError) as exc:
        RepositoryContract.validate(make_valid_payload(created_at=naive_dt))
    assert "must be timezone-aware" in str(exc.value)


def test_contract_fails_on_empty_branch_and_url() -> None:
    """Empty default_branch or html_url must raise ContractValidationError."""
    with pytest.raises(ContractValidationError) as exc:
        RepositoryContract.validate(make_valid_payload(default_branch="   "))
    assert "Field 'default_branch' must be a non-empty string" in str(exc.value)

    with pytest.raises(ContractValidationError) as exc2:
        RepositoryContract.validate(make_valid_payload(html_url=""))
    assert "Field 'html_url' must be a non-empty string" in str(exc2.value)
