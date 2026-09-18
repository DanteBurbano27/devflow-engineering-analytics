"""Run configurable GitHub repository extraction and local persistence."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from ingestion.common.config import ConfigurationError, Settings
from ingestion.common.logging import configure_logging
from ingestion.github.client import GitHubClient
from ingestion.github.repository_batch import (
    GitHubRepositoryBatch,
    RepositoryBatchConfigurationError,
    load_repository_config,
)
from ingestion.github.repository_service import GitHubRepositoryService


def build_parser() -> argparse.ArgumentParser:
    """Build the repository batch command-line parser."""
    parser = argparse.ArgumentParser(
        description="Extract configured GitHub repositories to local JSON files."
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to a repository configuration JSON file.",
    )
    parser.add_argument(
        "--output-root",
        required=True,
        type=Path,
        help="Root directory for raw, normalized and manifest outputs.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the repository batch and return its process exit code."""
    args = build_parser().parse_args(argv)

    try:
        config = load_repository_config(args.config)
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
        result = GitHubRepositoryBatch(service).run(
            config,
            output_root=args.output_root,
        )
    except (ConfigurationError, RepositoryBatchConfigurationError) as exc:
        print(f"[ERROR] {exc}")
        return 1
    except OSError:
        print("[ERROR] Local repository batch output could not be written.")
        return 1

    print("DevFlow Intelligence - Repository Batch Extraction")
    print("--------------------------------------------------")
    print(f"Run ID: {result.run_id}")
    print(f"Status: {result.status}")
    print(f"Repositories succeeded: {result.repositories_succeeded}")
    print(f"Repositories failed: {result.repositories_failed}")
    print(f"Manifest: {result.manifest_path}")

    return {
        "success": 0,
        "partial_success": 2,
        "failed": 1,
    }[result.status]


if __name__ == "__main__":
    raise SystemExit(main())
