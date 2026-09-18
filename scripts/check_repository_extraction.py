"""Validate repository metadata extraction against the GitHub API."""

from ingestion.common.config import ConfigurationError, Settings
from ingestion.common.logging import configure_logging
from ingestion.github.client import GitHubClient
from ingestion.github.exceptions import GitHubAPIError
from ingestion.github.repository_service import (
    GitHubRepositoryService,
    RepositoryExtractionError,
)


def main() -> int:
    """Extract and display normalized repository metadata."""
    try:
        settings = Settings.from_env()
        configure_logging(settings.log_level)

        client = GitHubClient(
            token=settings.github_token,
            base_url=settings.github_api_base_url,
            api_version=settings.github_api_version,
            timeout_seconds=settings.github_timeout_seconds,
            max_retries=settings.github_max_retries,
            backoff_seconds=settings.github_backoff_seconds,
        )

        service = GitHubRepositoryService(client)

        metadata = service.extract_repository(
            owner="apache",
            repository="airflow",
        )

    except (
        ConfigurationError,
        GitHubAPIError,
        RepositoryExtractionError,
        ValueError,
    ) as exc:
        print(f"[ERROR] {exc}")
        return 1

    print("DevFlow Intelligence - Repository Extraction Check")
    print("--------------------------------------------------")
    print("[SUCCESS] Repository metadata extracted.")
    print(f"Repository ID: {metadata.repository_id}")
    print(f"Repository: {metadata.full_name}")
    print(f"Owner: {metadata.owner_login}")
    print(f"Visibility: {metadata.visibility}")
    print(f"Default branch: {metadata.default_branch}")
    print(f"Language: {metadata.language}")
    print(f"Stars: {metadata.stars_count}")
    print(f"Forks: {metadata.forks_count}")
    print(f"Open issues: {metadata.open_issues_count}")
    print(f"Extracted at: {metadata.extracted_at.isoformat()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
