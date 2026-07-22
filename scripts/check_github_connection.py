"""Perform a manual connectivity check against the GitHub REST API."""

from typing import Any

from ingestion.common.config import ConfigurationError, Settings
from ingestion.github.client import GitHubClient
from ingestion.github.exceptions import GitHubAPIError


def require_mapping(
    value: object,
    description: str,
) -> dict[str, Any]:
    """Validate that an API response contains a JSON object."""
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected {description} to be a JSON object.")

    return value


def main() -> int:
    """Validate authentication and access to a public repository."""
    try:
        settings = Settings.from_env()

        client = GitHubClient(
            token=settings.github_token,
            base_url=settings.github_api_base_url,
            api_version=settings.github_api_version,
            timeout_seconds=settings.github_timeout_seconds,
        )

        rate_payload = require_mapping(
            client.get("/rate_limit"),
            "rate limit response",
        )

        resources = require_mapping(
            rate_payload.get("resources"),
            "rate limit resources",
        )

        core_rate = require_mapping(
            resources.get("core"),
            "core rate limit",
        )

        repository = require_mapping(
            client.get("/repos/apache/airflow"),
            "repository response",
        )

    except (ConfigurationError, GitHubAPIError, RuntimeError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    print("DevFlow Intelligence - GitHub Connection Check")
    print("----------------------------------------------")
    print("[SUCCESS] GitHub API connection established.")
    print(f"Repository: {repository.get('full_name')}")
    print(f"Default branch: {repository.get('default_branch')}")
    print(
        "Rate limit: "
        f"{core_rate.get('remaining')} remaining "
        f"of {core_rate.get('limit')}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
