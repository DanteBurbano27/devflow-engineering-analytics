"""Normalized repository metadata derived from GitHub API payloads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self


class RepositoryMetadataError(ValueError):
    """Raised when a GitHub repository payload is invalid."""


@dataclass(frozen=True, slots=True)
class RepositoryMetadata:
    """Stable representation of repository metadata for analytics."""

    repository_id: int
    repository_name: str
    full_name: str
    owner_login: str
    description: str | None
    visibility: str
    default_branch: str
    language: str | None
    is_fork: bool
    is_archived: bool
    is_disabled: bool
    created_at: datetime
    updated_at: datetime
    pushed_at: datetime | None
    stars_count: int
    forks_count: int
    open_issues_count: int
    subscribers_count: int
    size_kb: int
    html_url: str
    extracted_at: datetime

    @classmethod
    def from_github_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        extracted_at: datetime | None = None,
    ) -> Self:
        """Create normalized metadata from a GitHub API response."""
        owner = _require_mapping(
            payload.get("owner"),
            field_name="owner",
        )

        visibility = _require_string(
            payload,
            field_name="visibility",
        )

        valid_visibilities = {
            "public",
            "private",
            "internal",
        }

        if visibility not in valid_visibilities:
            raise RepositoryMetadataError(
                "Field 'visibility' must be public, private or internal."
            )

        normalized_extracted_at = (
            datetime.now(UTC)
            if extracted_at is None
            else _normalize_aware_datetime(
                extracted_at,
                field_name="extracted_at",
            )
        )

        return cls(
            repository_id=_require_non_negative_integer(
                payload,
                field_name="id",
            ),
            repository_name=_require_string(
                payload,
                field_name="name",
            ),
            full_name=_require_string(
                payload,
                field_name="full_name",
            ),
            owner_login=_require_string(
                owner,
                field_name="login",
                qualified_name="owner.login",
            ),
            description=_optional_string(
                payload,
                field_name="description",
            ),
            visibility=visibility,
            default_branch=_require_string(
                payload,
                field_name="default_branch",
            ),
            language=_optional_string(
                payload,
                field_name="language",
            ),
            is_fork=_require_boolean(
                payload,
                field_name="fork",
            ),
            is_archived=_require_boolean(
                payload,
                field_name="archived",
            ),
            is_disabled=_require_boolean(
                payload,
                field_name="disabled",
            ),
            created_at=_require_datetime(
                payload,
                field_name="created_at",
            ),
            updated_at=_require_datetime(
                payload,
                field_name="updated_at",
            ),
            pushed_at=_optional_datetime(
                payload,
                field_name="pushed_at",
            ),
            stars_count=_require_non_negative_integer(
                payload,
                field_name="stargazers_count",
            ),
            forks_count=_require_non_negative_integer(
                payload,
                field_name="forks_count",
            ),
            open_issues_count=_require_non_negative_integer(
                payload,
                field_name="open_issues_count",
            ),
            subscribers_count=_require_non_negative_integer(
                payload,
                field_name="subscribers_count",
            ),
            size_kb=_require_non_negative_integer(
                payload,
                field_name="size",
            ),
            html_url=_require_string(
                payload,
                field_name="html_url",
            ),
            extracted_at=normalized_extracted_at,
        )

    def to_record(self) -> dict[str, Any]:
        """Return a stable record suitable for analytical storage."""
        return {
            "repository_id": self.repository_id,
            "repository_name": self.repository_name,
            "full_name": self.full_name,
            "owner_login": self.owner_login,
            "description": self.description,
            "visibility": self.visibility,
            "default_branch": self.default_branch,
            "language": self.language,
            "is_fork": self.is_fork,
            "is_archived": self.is_archived,
            "is_disabled": self.is_disabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pushed_at": self.pushed_at,
            "stars_count": self.stars_count,
            "forks_count": self.forks_count,
            "open_issues_count": self.open_issues_count,
            "subscribers_count": self.subscribers_count,
            "size_kb": self.size_kb,
            "html_url": self.html_url,
            "extracted_at": self.extracted_at,
        }


def _require_mapping(
    value: object,
    *,
    field_name: str,
) -> Mapping[str, Any]:
    """Validate that a payload field contains an object."""
    if not isinstance(value, Mapping):
        raise RepositoryMetadataError(f"Field '{field_name}' must be a JSON object.")

    return value


def _require_string(
    payload: Mapping[str, Any],
    *,
    field_name: str,
    qualified_name: str | None = None,
) -> str:
    """Return a required non-empty string field."""
    value = payload.get(field_name)
    display_name = qualified_name or field_name

    if not isinstance(value, str) or not value.strip():
        raise RepositoryMetadataError(
            f"Field '{display_name}' must be a non-empty string."
        )

    return value.strip()


def _optional_string(
    payload: Mapping[str, Any],
    *,
    field_name: str,
) -> str | None:
    """Return an optional string field."""
    value = payload.get(field_name)

    if value is None:
        return None

    if not isinstance(value, str):
        raise RepositoryMetadataError(f"Field '{field_name}' must be a string or null.")

    return value


def _require_boolean(
    payload: Mapping[str, Any],
    *,
    field_name: str,
) -> bool:
    """Return a required boolean field."""
    value = payload.get(field_name)

    if not isinstance(value, bool):
        raise RepositoryMetadataError(f"Field '{field_name}' must be a boolean.")

    return value


def _require_non_negative_integer(
    payload: Mapping[str, Any],
    *,
    field_name: str,
) -> int:
    """Return a required non-negative integer field."""
    value = payload.get(field_name)

    if isinstance(value, bool) or not isinstance(value, int):
        raise RepositoryMetadataError(f"Field '{field_name}' must be an integer.")

    if value < 0:
        raise RepositoryMetadataError(f"Field '{field_name}' cannot be negative.")

    return value


def _require_datetime(
    payload: Mapping[str, Any],
    *,
    field_name: str,
) -> datetime:
    """Return a required timezone-aware datetime field."""
    value = payload.get(field_name)

    return _parse_datetime(
        value,
        field_name=field_name,
    )


def _optional_datetime(
    payload: Mapping[str, Any],
    *,
    field_name: str,
) -> datetime | None:
    """Return an optional timezone-aware datetime field."""
    value = payload.get(field_name)

    if value is None:
        return None

    return _parse_datetime(
        value,
        field_name=field_name,
    )


def _parse_datetime(
    value: object,
    *,
    field_name: str,
) -> datetime:
    """Parse one ISO 8601 datetime value."""
    if not isinstance(value, str) or not value.strip():
        raise RepositoryMetadataError(
            f"Field '{field_name}' must be an ISO 8601 datetime."
        )

    normalized_value = value.strip()

    if normalized_value.endswith("Z"):
        normalized_value = f"{normalized_value[:-1]}+00:00"

    try:
        parsed_value = datetime.fromisoformat(normalized_value)
    except ValueError as exc:
        raise RepositoryMetadataError(
            f"Field '{field_name}' contains an invalid datetime."
        ) from exc

    return _normalize_aware_datetime(
        parsed_value,
        field_name=field_name,
    )


def _normalize_aware_datetime(
    value: datetime,
    *,
    field_name: str,
) -> datetime:
    """Normalize an aware datetime to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise RepositoryMetadataError(
            f"Field '{field_name}' must include timezone information."
        )

    return value.astimezone(UTC)
