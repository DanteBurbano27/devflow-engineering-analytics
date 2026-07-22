"""Reusable HTTP client for the GitHub REST API."""

from __future__ import annotations

from typing import Any, TypeAlias

import requests
from requests import Response, Session
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
)
from requests.exceptions import (
    HTTPError,
    JSONDecodeError,
    Timeout,
)

from ingestion.github.exceptions import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)

JSONData: TypeAlias = dict[str, Any] | list[Any]


class GitHubClient:
    """Client responsible for sending authenticated requests to GitHub."""

    def __init__(
        self,
        token: str,
        base_url: str = "https://api.github.com",
        api_version: str = "2026-03-10",
        timeout_seconds: float = 30.0,
        session: Session | None = None,
    ) -> None:
        """Initialize the GitHub API client."""
        clean_token = token.strip()

        if not clean_token:
            raise ValueError("A GitHub token is required.")

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")

        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()

        self._session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {clean_token}",
                "X-GitHub-Api-Version": api_version,
                "User-Agent": "devflow-engineering-analytics",
            }
        )

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> JSONData:
        """Send a GET request and return the decoded JSON response."""
        url = self._build_url(endpoint)
        response = self._send_get(url=url, params=params)

        self._raise_for_status(response)

        try:
            payload = response.json()
        except JSONDecodeError as exc:
            raise GitHubAPIError(
                f"GitHub returned an invalid JSON response for {url}."
            ) from exc

        if not isinstance(payload, (dict, list)):
            raise GitHubAPIError(
                f"GitHub returned an unsupported JSON structure for {url}."
            )

        return payload

    def _send_get(
        self,
        url: str,
        params: dict[str, Any] | None,
    ) -> Response:
        """Send a GET request while handling network-level failures."""
        try:
            return self._session.get(
                url,
                params=params,
                timeout=self._timeout_seconds,
            )
        except Timeout as exc:
            raise GitHubAPIError(
                f"The GitHub request timed out after {self._timeout_seconds} seconds."
            ) from exc
        except RequestsConnectionError as exc:
            raise GitHubAPIError("The connection to the GitHub API failed.") from exc

    def _raise_for_status(self, response: Response) -> None:
        """Convert relevant HTTP status codes into domain exceptions."""
        status_code = response.status_code
        request_url = response.url

        if status_code == 401:
            raise GitHubAuthenticationError(
                "GitHub rejected the token. Verify GITHUB_TOKEN."
            )

        if status_code == 404:
            raise GitHubNotFoundError(
                f"The requested GitHub resource was not found: {request_url}"
            )

        if status_code in {403, 429}:
            remaining = response.headers.get("x-ratelimit-remaining")
            reset_at = response.headers.get("x-ratelimit-reset")
            retry_after = response.headers.get("retry-after")

            if remaining == "0" or retry_after is not None:
                raise GitHubRateLimitError(
                    "GitHub API rate limit reached. "
                    f"Remaining={remaining}, "
                    f"reset_at={reset_at}, "
                    f"retry_after={retry_after}."
                )

            raise GitHubAPIError(
                f"GitHub rejected the request with status {status_code}."
            )

        try:
            response.raise_for_status()
        except HTTPError as exc:
            raise GitHubAPIError(
                f"GitHub request failed with status {status_code}: {request_url}"
            ) from exc

    def _build_url(self, endpoint: str) -> str:
        """Build a complete GitHub API URL from a relative endpoint."""
        clean_endpoint = endpoint.strip()

        if not clean_endpoint:
            raise ValueError("The endpoint cannot be empty.")

        if not clean_endpoint.startswith("/"):
            clean_endpoint = f"/{clean_endpoint}"

        return f"{self._base_url}{clean_endpoint}"
