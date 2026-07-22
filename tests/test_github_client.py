"""Unit tests for the reusable GitHub API client."""

import json
from unittest.mock import Mock

import pytest
from requests import Response, Session
from requests.exceptions import Timeout

from ingestion.github.client import GitHubClient
from ingestion.github.exceptions import (
    GitHubAPIError,
    GitHubRateLimitError,
)


def build_response(
    payload: object,
    url: str,
    status_code: int = 200,
    link_header: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> Response:
    """Create a simulated requests response."""
    response = Response()
    response.status_code = status_code
    response.url = url
    response._content = json.dumps(payload).encode("utf-8")
    response.headers["Content-Type"] = "application/json"

    if link_header:
        response.headers["Link"] = link_header

    if extra_headers:
        response.headers.update(extra_headers)

    return response


def build_session(*side_effects: object) -> Mock:
    """Create a simulated HTTP session."""
    session = Mock(spec=Session)
    session.headers = {}
    session.get.side_effect = side_effects

    return session


def test_get_returns_json_object() -> None:
    """A normal GET request must return the decoded JSON object."""
    response = build_response(
        payload={
            "id": 1,
            "full_name": "apache/airflow",
        },
        url="https://api.github.com/repos/apache/airflow",
    )

    session = build_session(response)

    client = GitHubClient(
        token="test-token",
        session=session,
    )

    result = client.get("/repos/apache/airflow")

    assert result == {
        "id": 1,
        "full_name": "apache/airflow",
    }

    session.get.assert_called_once_with(
        "https://api.github.com/repos/apache/airflow",
        params=None,
        timeout=30.0,
    )


def test_get_all_pages_combines_multiple_pages() -> None:
    """The client must combine the items returned by all pages."""
    second_page_url = (
        "https://api.github.com/repos/apache/airflow/"
        "pulls?state=all&per_page=100&page=2"
    )

    first_response = build_response(
        payload=[
            {"id": 1},
            {"id": 2},
        ],
        url=(
            "https://api.github.com/repos/apache/airflow/pulls?state=all&per_page=100"
        ),
        link_header=f'<{second_page_url}>; rel="next"',
    )

    second_response = build_response(
        payload=[
            {"id": 3},
            {"id": 4},
        ],
        url=second_page_url,
    )

    session = build_session(
        first_response,
        second_response,
    )

    client = GitHubClient(
        token="test-token",
        session=session,
    )

    result = client.get_all_pages(
        endpoint="/repos/apache/airflow/pulls",
        params={"state": "all"},
    )

    assert result == [
        {"id": 1},
        {"id": 2},
        {"id": 3},
        {"id": 4},
    ]

    assert session.get.call_count == 2

    first_call = session.get.call_args_list[0]
    second_call = session.get.call_args_list[1]

    assert first_call.kwargs["params"] == {
        "state": "all",
        "per_page": 100,
    }

    assert second_call.args[0] == second_page_url
    assert second_call.kwargs["params"] is None


def test_get_all_pages_rejects_non_list_response() -> None:
    """A paginated endpoint must return a JSON list."""
    response = build_response(
        payload={"message": "unexpected object"},
        url="https://api.github.com/repos/apache/airflow/pulls",
    )

    session = build_session(response)

    client = GitHubClient(
        token="test-token",
        session=session,
    )

    with pytest.raises(
        GitHubAPIError,
        match="must return a JSON list",
    ):
        client.get_all_pages("/repos/apache/airflow/pulls")


def test_get_all_pages_rejects_invalid_max_pages() -> None:
    """The maximum page count must be a positive number."""
    client = GitHubClient(token="test-token")

    with pytest.raises(
        ValueError,
        match="max_pages must be greater than zero",
    ):
        client.get_all_pages(
            "/repos/apache/airflow/pulls",
            max_pages=0,
        )


def test_get_retries_after_timeout() -> None:
    """A timeout must be retried before returning a successful response."""
    successful_response = build_response(
        payload={"id": 1},
        url="https://api.github.com/repos/apache/airflow",
    )

    session = build_session(
        Timeout("temporary timeout"),
        successful_response,
    )

    sleeper = Mock()

    client = GitHubClient(
        token="test-token",
        session=session,
        max_retries=2,
        backoff_seconds=1,
        sleeper=sleeper,
    )

    result = client.get("/repos/apache/airflow")

    assert result == {"id": 1}
    assert session.get.call_count == 2
    sleeper.assert_called_once_with(1)


def test_get_retries_temporary_server_error() -> None:
    """A temporary server error must be retried."""
    temporary_failure = build_response(
        payload={"message": "Service unavailable"},
        url="https://api.github.com/repos/apache/airflow",
        status_code=503,
    )

    successful_response = build_response(
        payload={"id": 1},
        url="https://api.github.com/repos/apache/airflow",
    )

    session = build_session(
        temporary_failure,
        successful_response,
    )

    sleeper = Mock()

    client = GitHubClient(
        token="test-token",
        session=session,
        max_retries=2,
        backoff_seconds=1,
        sleeper=sleeper,
    )

    result = client.get("/repos/apache/airflow")

    assert result == {"id": 1}
    assert session.get.call_count == 2
    sleeper.assert_called_once_with(1)


def test_get_raises_after_exhausting_network_retries() -> None:
    """The client must fail after exhausting its retry allowance."""
    session = build_session(
        Timeout("first timeout"),
        Timeout("second timeout"),
        Timeout("third timeout"),
    )

    sleeper = Mock()

    client = GitHubClient(
        token="test-token",
        session=session,
        max_retries=2,
        backoff_seconds=1,
        sleeper=sleeper,
    )

    with pytest.raises(
        GitHubAPIError,
        match="failed after 3 attempts",
    ):
        client.get("/repos/apache/airflow")

    assert session.get.call_count == 3

    assert sleeper.call_args_list == [
        ((1,), {}),
        ((2,), {}),
    ]


def test_rate_limit_error_contains_response_metadata() -> None:
    """Rate-limit metadata must be exposed through the exception."""
    response = build_response(
        payload={"message": "API rate limit exceeded"},
        url="https://api.github.com/rate_limit",
        status_code=403,
        extra_headers={
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "1784757600",
        },
    )

    session = build_session(response)

    client = GitHubClient(
        token="test-token",
        session=session,
    )

    with pytest.raises(GitHubRateLimitError) as exception_info:
        client.get("/rate_limit")

    error = exception_info.value

    assert error.remaining == "0"
    assert error.reset_at == "1784757600"
    assert error.retry_after is None
