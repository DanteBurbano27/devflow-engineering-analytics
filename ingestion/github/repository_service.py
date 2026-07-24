"""Service for extracting normalized GitHub repository metadata."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ingestion.github.client import GitHubClient
from ingestion.github.repository_metadata import (
    RepositoryMetadata,
    RepositoryMetadataError,
)

logger = logging.getLogger(__name__)


class RepositoryExtractionError(RuntimeError):
    """Raised when repository metadata cannot be extracted or normalized."""


@dataclass(frozen=True, slots=True)
class RepositoryExtractionResult:
    """Raw and normalized results produced by one GitHub request."""

    endpoint: str
    payload: dict[str, Any]
    metadata: RepositoryMetadata


class GitHubRepositoryService:
    """Extract and normalize repository metadata from GitHub."""

    def __init__(self, client: GitHubClient) -> None:
        """Initialize the service with a reusable GitHub API client."""
        self._client = client

    def extract_repository(
        self,
        owner: str,
        repository: str,
        *,
        extracted_at: datetime | None = None,
    ) -> RepositoryMetadata:
        """Extract and normalize metadata for one GitHub repository."""
        return self.extract_repository_with_payload(
            owner,
            repository,
            extracted_at=extracted_at,
        ).metadata

    def extract_repository_with_payload(
        self,
        owner: str,
        repository: str,
        *,
        extracted_at: datetime | None = None,
    ) -> RepositoryExtractionResult:
        """Extract raw and normalized metadata with a single GitHub request."""
        normalized_owner = _normalize_path_component(
            owner,
            field_name="owner",
        )

        normalized_repository = _normalize_path_component(
            repository,
            field_name="repository",
        )

        endpoint = f"/repos/{normalized_owner}/{normalized_repository}"

        logger.info(
            "Starting GitHub repository metadata extraction.",
            extra={
                "operation": "github_repository_extraction",
                "owner": normalized_owner,
                "repository": normalized_repository,
                "endpoint": endpoint,
            },
        )

        payload = self._client.get(endpoint)

        if not isinstance(payload, dict):
            raise RepositoryExtractionError(
                "GitHub repository endpoint returned a non-object JSON response."
            )

        try:
            metadata = RepositoryMetadata.from_github_payload(
                payload,
                extracted_at=extracted_at,
            )
        except RepositoryMetadataError as exc:
            raise RepositoryExtractionError(
                "GitHub repository metadata could not be normalized "
                f"for {normalized_owner}/{normalized_repository}."
            ) from exc

        logger.info(
            "GitHub repository metadata extraction completed.",
            extra={
                "operation": "github_repository_extraction",
                "repository_id": metadata.repository_id,
                "full_name": metadata.full_name,
                "owner": metadata.owner_login,
                "visibility": metadata.visibility,
            },
        )

        return RepositoryExtractionResult(
            endpoint=endpoint,
            payload=payload,
            metadata=metadata,
        )


def _normalize_path_component(
    value: str,
    *,
    field_name: str,
) -> str:
    """Validate one GitHub repository path component."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(f"{field_name} cannot be empty.")

    if "/" in normalized_value or "\\" in normalized_value:
        raise ValueError(f"{field_name} cannot contain path separators.")

    return normalized_value
