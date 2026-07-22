"""Tests for normalized GitHub repository metadata."""

from datetime import UTC, datetime

import pytest

from ingestion.github.repository_metadata import (
    RepositoryMetadata,
    RepositoryMetadataError,
)

VALID_PAYLOAD = {
    "id": 1296269,
    "name": "Hello-World",
    "full_name": "octocat/Hello-World",
    "owner": {
        "login": "octocat",
    },
    "description": "Example repository",
    "visibility": "public",
    "default_branch": "main",
    "language": "Python",
    "fork": False,
    "archived": False,
    "disabled": False,
    "created_at": "2011-01-26T19:01:12Z",
    "updated_at": "2011-01-26T19:14:43Z",
    "pushed_at": "2011-01-26T19:06:43Z",
    "stargazers_count": 80,
    "forks_count": 9,
    "open_issues_count": 2,
    "subscribers_count": 42,
    "size": 108,
    "html_url": "https://github.com/octocat/Hello-World",
}


def test_from_github_payload_normalizes_repository() -> None:
    """A valid GitHub payload must produce normalized metadata."""
    extracted_at = datetime(
        2026,
        7,
        22,
        21,
        45,
        tzinfo=UTC,
    )

    metadata = RepositoryMetadata.from_github_payload(
        VALID_PAYLOAD,
        extracted_at=extracted_at,
    )

    assert metadata.repository_id == 1296269
    assert metadata.repository_name == "Hello-World"
    assert metadata.full_name == "octocat/Hello-World"
    assert metadata.owner_login == "octocat"
    assert metadata.visibility == "public"
    assert metadata.default_branch == "main"
    assert metadata.language == "Python"
    assert metadata.stars_count == 80
    assert metadata.forks_count == 9
    assert metadata.open_issues_count == 2
    assert metadata.subscribers_count == 42
    assert metadata.size_kb == 108
    assert metadata.extracted_at == extracted_at

    assert metadata.created_at == datetime(
        2011,
        1,
        26,
        19,
        1,
        12,
        tzinfo=UTC,
    )


def test_to_record_returns_stable_analytical_shape() -> None:
    """The normalized record must expose the expected warehouse columns."""
    metadata = RepositoryMetadata.from_github_payload(
        VALID_PAYLOAD,
    )

    record = metadata.to_record()

    assert set(record) == {
        "repository_id",
        "repository_name",
        "full_name",
        "owner_login",
        "description",
        "visibility",
        "default_branch",
        "language",
        "is_fork",
        "is_archived",
        "is_disabled",
        "created_at",
        "updated_at",
        "pushed_at",
        "stars_count",
        "forks_count",
        "open_issues_count",
        "subscribers_count",
        "size_kb",
        "html_url",
        "extracted_at",
    }

    assert record["full_name"] == "octocat/Hello-World"
    assert record["stars_count"] == 80


def test_nullable_repository_fields_are_supported() -> None:
    """Nullable fields returned by GitHub must remain nullable."""
    payload = {
        **VALID_PAYLOAD,
        "description": None,
        "language": None,
        "pushed_at": None,
    }

    metadata = RepositoryMetadata.from_github_payload(payload)

    assert metadata.description is None
    assert metadata.language is None
    assert metadata.pushed_at is None


def test_missing_owner_login_is_rejected() -> None:
    """A repository without an owner login must be rejected."""
    payload = {
        **VALID_PAYLOAD,
        "owner": {},
    }

    with pytest.raises(
        RepositoryMetadataError,
        match="owner.login",
    ):
        RepositoryMetadata.from_github_payload(payload)


def test_negative_repository_metric_is_rejected() -> None:
    """Repository counters cannot contain negative values."""
    payload = {
        **VALID_PAYLOAD,
        "stargazers_count": -1,
    }

    with pytest.raises(
        RepositoryMetadataError,
        match="stargazers_count.*cannot be negative",
    ):
        RepositoryMetadata.from_github_payload(payload)


def test_naive_extraction_datetime_is_rejected() -> None:
    """The extraction timestamp must include timezone information."""
    naive_datetime = datetime(
        2026,
        7,
        22,
        21,
        45,
    )

    with pytest.raises(
        RepositoryMetadataError,
        match="extracted_at.*timezone",
    ):
        RepositoryMetadata.from_github_payload(
            VALID_PAYLOAD,
            extracted_at=naive_datetime,
        )
