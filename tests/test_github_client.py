"""Unit tests for the reusable GitHub API client."""

import json
from unittest.mock import Mock

import pytest
from requests import Response, Session

from ingestion.github.client import GitHubClient
from ingestion.github.exceptions import GitHubAPIError


def build_response(
    payload: object,
    url: str,
    status_code: int = 200,
    link_header: str | None = None,
) -> Response:
    """Create a simulated requests response."""
    response = Response()
    response.status_code = status_code
    response.url = url
    response._content = json.dumps(payload).encode("utf-8")
    response.headers["Content-Type"] = "application/json"

    if link_header:
        response.headers["Link"] = link_header

    return response


def build_session(*responses: Response) -> Mock:
    """Create a simulated HTTP session."""
    session = Mock(spec=Session)
    session.headers = {}
    session.get.side_effect = responses

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
