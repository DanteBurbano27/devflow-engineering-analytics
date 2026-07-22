"""Reusable HTTP client for the GitHub REST API."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

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

type JSONData = dict[str, Any] | list[Any]
type Sleeper = Callable[[float], None]

_RETRYABLE_STATUS_CODES = frozenset(
    {
        408,
        500,
        502,
        503,
        504,
    }
)

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client responsible for sending authenticated requests to GitHub."""

    def __init__(
        self,
        token: str,
        base_url: str = "https://api.github.com",
        api_version: str = "2026-03-10",
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        session: Session | None = None,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        """Initialize the GitHub API client."""
        clean_token = token.strip()

        if not clean_token:
            raise ValueError("A GitHub token is required.")

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")

        if max_retries < 0:
            raise ValueError("max_retries cannot be negative.")

        if backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative.")

        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._session = session or requests.Session()
        self._sleeper = sleeper

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
        """Send one GET request and return its decoded JSON response."""
        url = self._build_url(endpoint)

        response = self._send_get(
            url=url,
            params=params,
        )

        self._raise_for_status(response)

        return self._decode_json(
            response=response,
            request_url=url,
        )

    def get_all_pages(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        max_pages: int | None = None,
    ) -> list[Any]:
        """Retrieve and combine every page from a collection endpoint."""
        if max_pages is not None and max_pages <= 0:
            raise ValueError("max_pages must be greater than zero.")

        url = self._build_url(endpoint)

        request_params = dict(params or {})
        request_params.setdefault("per_page", 100)

        all_items: list[Any] = []
        page_count = 0

        while url:
            response = self._send_get(
                url=url,
                params=request_params,
            )

            self._raise_for_status(response)

            payload = self._decode_json(
                response=response,
                request_url=url,
            )

            if not isinstance(payload, list):
                raise GitHubAPIError(
                    "A paginated GitHub endpoint must return a JSON list."
                )

            all_items.extend(payload)
            page_count += 1

            logger.info(
                "GitHub page processed.",
                extra={
                    "operation": "github_pagination",
                    "page_number": page_count,
                    "page_item_count": len(payload),
                    "total_item_count": len(all_items),
                },
            )

            if max_pages is not None and page_count >= max_pages:
                break

            next_url = response.links.get("next", {}).get("url")

            if isinstance(next_url, str):
                url = next_url
            else:
                url = ""

            # GitHub's next URL already includes its query parameters.
            request_params = None

        return all_items

    def _send_get(
        self,
        url: str,
        params: dict[str, Any] | None,
    ) -> Response:
        """Send a GET request with retry handling."""
        max_attempts = self._max_retries + 1

        for attempt in range(1, max_attempts + 1):
            try:
                response = self._session.get(
                    url,
                    params=params,
                    timeout=self._timeout_seconds,
                )

            except (Timeout, RequestsConnectionError) as exc:
                if attempt >= max_attempts:
                    logger.error(
                        "GitHub request exhausted all retry attempts.",
                        extra={
                            "operation": "github_get",
                            "url": url,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "error_type": type(exc).__name__,
                        },
                    )

                    raise GitHubAPIError(
                        f"The GitHub request failed after {max_attempts} attempts."
                    ) from exc

                retry_delay = self._calculate_backoff(attempt)

                logger.warning(
                    "Retrying GitHub request after network failure.",
                    extra={
                        "operation": "github_get",
                        "url": url,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "retry_delay_seconds": retry_delay,
                        "error_type": type(exc).__name__,
                    },
                )

                self._sleeper(retry_delay)
                continue

            if (
                response.status_code in _RETRYABLE_STATUS_CODES
                and attempt < max_attempts
            ):
                retry_delay = self._retry_delay_for_response(
                    response=response,
                    attempt=attempt,
                )

                logger.warning(
                    "Retrying GitHub request after temporary HTTP failure.",
                    extra={
                        "operation": "github_get",
                        "url": url,
                        "status_code": response.status_code,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "retry_delay_seconds": retry_delay,
                    },
                )

                self._sleeper(retry_delay)
                continue

            logger.info(
                "GitHub request completed.",
                extra={
                    "operation": "github_get",
                    "url": url,
                    "status_code": response.status_code,
                    "attempt": attempt,
                    "rate_limit_remaining": response.headers.get(
                        "x-ratelimit-remaining"
                    ),
                },
            )

            return response

        raise RuntimeError("Unreachable GitHub retry-loop state.")

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate an exponential retry delay."""
        return self._backoff_seconds * (2 ** (attempt - 1))

    def _retry_delay_for_response(
        self,
        response: Response,
        attempt: int,
    ) -> float:
        """Determine the retry delay for a temporary HTTP response."""
        retry_after = response.headers.get("retry-after")

        if retry_after is not None:
            try:
                parsed_retry_after = float(retry_after)
            except ValueError:
                pass
            else:
                return max(parsed_retry_after, 0.0)

        return self._calculate_backoff(attempt)

    def _decode_json(
        self,
        response: Response,
        request_url: str,
    ) -> JSONData:
        """Decode and validate a GitHub JSON response."""
        try:
            payload = response.json()
        except JSONDecodeError as exc:
            raise GitHubAPIError(
                f"GitHub returned invalid JSON for {request_url}."
            ) from exc

        if not isinstance(payload, (dict, list)):
            raise GitHubAPIError(
                f"GitHub returned an unsupported JSON structure for {request_url}."
            )

        return payload

    def _extract_error_message(self, response: Response) -> str:
        """Extract the GitHub error message when available."""
        try:
            payload = response.json()
        except ValueError:
            return ""

        if not isinstance(payload, dict):
            return ""

        message = payload.get("message")

        if isinstance(message, str):
            return message

        return ""

    def _raise_for_status(self, response: Response) -> None:
        """Convert relevant HTTP status codes into domain exceptions."""
        status_code = response.status_code
        request_url = response.url
        github_message = self._extract_error_message(response)

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

            normalized_message = github_message.lower()

            is_rate_limit = (
                status_code == 429
                or remaining == "0"
                or retry_after is not None
                or "rate limit" in normalized_message
                or "abuse" in normalized_message
            )

            if is_rate_limit:
                raise GitHubRateLimitError(
                    "GitHub API rate limit reached. "
                    f"Remaining={remaining}, "
                    f"reset_at={reset_at}, "
                    f"retry_after={retry_after}.",
                    remaining=remaining,
                    reset_at=reset_at,
                    retry_after=retry_after,
                )

            raise GitHubAPIError(
                "GitHub rejected the request with status 403. "
                f"Message={github_message or 'Forbidden'}."
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
