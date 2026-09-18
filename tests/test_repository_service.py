"""Tests for the GitHub repository extraction service."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from ingestion.github.client import GitHubClient
from ingestion.github.repository_service import (
    GitHubRepositoryService,
    RepositoryExtractionError,
)


def build_repository_payload() -> dict[str, object]:
    """Build a valid simulated GitHub repository response."""
    return {
        "id": 1296269,
        "name": "airflow",
        "full_name": "apache/airflow",
        "owner": {
            "login": "apache",
        },
        "description": "Platform to programmatically author workflows",
        "visibility": "public",
        "default_branch": "main",
        "language": "Python",
        "fork": False,
        "archived": False,
        "disabled": False,
        "created_at": "2015-04-13T18:04:58Z",
        "updated_at": "2026-07-22T20:00:00Z",
        "pushed_at": "2026-07-22T19:30:00Z",
        "stargazers_count": 40000,
        "forks_count": 15000,
        "open_issues_count": 1000,
        "subscribers_count": 700,
        "size": 250000,
        "html_url": "https://github.com/apache/airflow",
    }


def test_extract_repository_returns_normalized_metadata() -> None:
    """A valid GitHub response must be normalized by the service."""
    client = Mock(spec=GitHubClient)
    client.get.return_value = build_repository_payload()

    service = GitHubRepositoryService(client)

    extracted_at = datetime(
        2026,
        7,
        22,
        22,
        0,
        tzinfo=UTC,
    )

    metadata = service.extract_repository(
        owner=" apache ",
        repository=" airflow ",
        extracted_at=extracted_at,
    )

    client.get.assert_called_once_with("/repos/apache/airflow")

    assert metadata.repository_id == 1296269
    assert metadata.full_name == "apache/airflow"
    assert metadata.owner_login == "apache"
    assert metadata.default_branch == "main"
    assert metadata.language == "Python"
    assert metadata.extracted_at == extracted_at


def test_extract_repository_with_payload_returns_structured_result() -> None:
    """The extended service must expose raw and normalized data from one request."""
    payload = build_repository_payload()
    client = Mock(spec=GitHubClient)
    client.get.return_value = payload
    service = GitHubRepositoryService(client)

    result = service.extract_repository_with_payload(
        owner="apache",
        repository="airflow",
    )

    client.get.assert_called_once_with("/repos/apache/airflow")
    assert result.endpoint == "/repos/apache/airflow"
    assert result.payload is payload
    assert result.metadata.full_name == "apache/airflow"


def test_extract_repository_rejects_non_object_response() -> None:
    """The repository endpoint must return a JSON object."""
    client = Mock(spec=GitHubClient)
    client.get.return_value = []

    service = GitHubRepositoryService(client)

    with pytest.raises(
        RepositoryExtractionError,
        match="non-object JSON response",
    ):
        service.extract_repository(
            owner="apache",
            repository="airflow",
        )


def test_extract_repository_wraps_normalization_error() -> None:
    """Invalid GitHub metadata must produce an extraction error."""
    invalid_payload = build_repository_payload()
    invalid_payload["owner"] = {}

    client = Mock(spec=GitHubClient)
    client.get.return_value = invalid_payload

    service = GitHubRepositoryService(client)

    with pytest.raises(
        RepositoryExtractionError,
        match="could not be normalized",
    ) as exception_info:
        service.extract_repository(
            owner="apache",
            repository="airflow",
        )

    assert exception_info.value.__cause__ is not None


def test_extract_repository_rejects_path_separator() -> None:
    """Repository path components cannot contain separators."""
    client = Mock(spec=GitHubClient)
    service = GitHubRepositoryService(client)

    with pytest.raises(
        ValueError,
        match="owner cannot contain path separators",
    ):
        service.extract_repository(
            owner="apache/team",
            repository="airflow",
        )

    client.get.assert_not_called()
