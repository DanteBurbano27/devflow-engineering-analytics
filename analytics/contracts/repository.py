"""Repository data contract definition and enforcement.

Defines the analytical schema contract for GitHub repository metadata records,
ensuring explicit typing, nullability constraints, and timestamp semantics.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from ingestion.github.repository_metadata import RepositoryMetadata


class ContractValidationError(ValueError):
    """Raised when an incoming record violates the repository contract."""

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        details: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.details = details or []


@dataclass(frozen=True, slots=True)
class ContractFieldDefinition:
    """Metadata describing a single contract field."""

    name: str
    data_type: str
    nullable: bool
    is_primary_key: bool
    description: str


@dataclass(frozen=True, slots=True)
class ContractSchema:
    """Analytical schema specification for repository metadata."""

    name: str
    version: str
    primary_key: tuple[str, ...]
    fields: tuple[ContractFieldDefinition, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize schema definition to dictionary."""
        return {
            "schema_name": self.name,
            "version": self.version,
            "primary_key": list(self.primary_key),
            "fields": [asdict(f) for f in self.fields],
        }


@dataclass(frozen=True, slots=True)
class RepositoryRecord:
    """Immutable, typed, validated analytical representation of a repository."""

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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary suitable for JSON and warehouse loading."""
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
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "pushed_at": self.pushed_at.isoformat() if self.pushed_at else None,
            "stars_count": self.stars_count,
            "forks_count": self.forks_count,
            "open_issues_count": self.open_issues_count,
            "subscribers_count": self.subscribers_count,
            "size_kb": self.size_kb,
            "html_url": self.html_url,
            "extracted_at": self.extracted_at.isoformat(),
        }


class RepositoryContract:
    """Enforces analytical data contract standards for repository records."""

    SCHEMA_VERSION: str = "1.0.0"
    VALID_VISIBILITIES: frozenset[str] = frozenset({"public", "private", "internal"})

    _SCHEMA = ContractSchema(
        name="repository_metadata_contract",
        version=SCHEMA_VERSION,
        primary_key=("repository_id", "full_name"),
        fields=(
            ContractFieldDefinition(
                "repository_id", "int", False, True, "GitHub repository unique ID"
            ),
            ContractFieldDefinition(
                "repository_name", "str", False, False, "Short repository name"
            ),
            ContractFieldDefinition(
                "full_name", "str", False, True, "Full canonical name (owner/repo)"
            ),
            ContractFieldDefinition(
                "owner_login", "str", False, False, "Repository owner username or org"
            ),
            ContractFieldDefinition(
                "description", "str", True, False, "Repository description text"
            ),
            ContractFieldDefinition(
                "visibility",
                "str",
                False,
                False,
                "Visibility: public, private, or internal",
            ),
            ContractFieldDefinition(
                "default_branch", "str", False, False, "Default git branch name"
            ),
            ContractFieldDefinition(
                "language", "str", True, False, "Primary programming language"
            ),
            ContractFieldDefinition(
                "is_fork", "bool", False, False, "Whether repository is a fork"
            ),
            ContractFieldDefinition(
                "is_archived", "bool", False, False, "Whether repository is archived"
            ),
            ContractFieldDefinition(
                "is_disabled", "bool", False, False, "Whether repository is disabled"
            ),
            ContractFieldDefinition(
                "created_at",
                "datetime",
                False,
                False,
                "UTC timestamp when repository was created",
            ),
            ContractFieldDefinition(
                "updated_at",
                "datetime",
                False,
                False,
                "UTC timestamp when repository was updated",
            ),
            ContractFieldDefinition(
                "pushed_at",
                "datetime",
                True,
                False,
                "UTC timestamp of last push (null if none)",
            ),
            ContractFieldDefinition(
                "stars_count",
                "int",
                False,
                False,
                "Number of GitHub stars (non-negative)",
            ),
            ContractFieldDefinition(
                "forks_count",
                "int",
                False,
                False,
                "Number of repository forks (non-negative)",
            ),
            ContractFieldDefinition(
                "open_issues_count",
                "int",
                False,
                False,
                "Number of open issues and pull requests (non-negative)",
            ),
            ContractFieldDefinition(
                "subscribers_count",
                "int",
                False,
                False,
                "Number of watchers (non-negative)",
            ),
            ContractFieldDefinition(
                "size_kb", "int", False, False, "Repository size in KB (non-negative)"
            ),
            ContractFieldDefinition(
                "html_url", "str", False, False, "Canonical GitHub web URL"
            ),
            ContractFieldDefinition(
                "extracted_at",
                "datetime",
                False,
                False,
                "UTC timestamp when data was ingested",
            ),
        ),
    )

    @classmethod
    def get_schema(cls) -> ContractSchema:
        """Return the immutable schema specification."""
        return cls._SCHEMA

    @classmethod
    def validate(
        cls, item: RepositoryMetadata | Mapping[str, Any] | RepositoryRecord
    ) -> RepositoryRecord:
        """Validate input item against contract and return normalized RepositoryRecord.

        Raises ContractValidationError if item violates contract schema.
        """
        if isinstance(item, RepositoryRecord):
            return item

        if isinstance(item, RepositoryMetadata):
            record_dict = item.to_record()
        elif isinstance(item, Mapping):
            record_dict = dict(item)
        else:
            raise ContractValidationError(
                f"Unsupported record type: expected RepositoryMetadata or Mapping, "
                f"got {type(item).__name__}"
            )

        errors: list[str] = []

        # 1. repository_id
        repo_id = record_dict.get("repository_id")
        if repo_id is None or isinstance(repo_id, bool) or not isinstance(repo_id, int):
            errors.append("Field 'repository_id' must be an integer.")
        elif repo_id <= 0:
            errors.append(
                f"Field 'repository_id' must be a positive integer, got {repo_id}."
            )

        # 2. repository_name
        repo_name = record_dict.get("repository_name")
        if not isinstance(repo_name, str) or not repo_name.strip():
            errors.append("Field 'repository_name' must be a non-empty string.")

        # 3. full_name
        full_name = record_dict.get("full_name")
        if not isinstance(full_name, str) or not full_name.strip():
            errors.append("Field 'full_name' must be a non-empty string.")
        elif "/" not in full_name:
            errors.append(
                f"Field 'full_name' must match 'owner/repo' pattern, got '{full_name}'."
            )

        # 4. owner_login
        owner_login = record_dict.get("owner_login")
        if not isinstance(owner_login, str) or not owner_login.strip():
            errors.append("Field 'owner_login' must be a non-empty string.")

        # Consistency check: full_name starts with owner_login/
        if (
            isinstance(full_name, str)
            and isinstance(owner_login, str)
            and owner_login.strip()
        ):
            expected_prefix = f"{owner_login.strip()}/"
            if not full_name.strip().startswith(expected_prefix):
                errors.append(
                    f"Inconsistent identity: full_name '{full_name}' "
                    f"does not start with owner '{owner_login}'."
                )

        # 5. description (nullable string)
        description = record_dict.get("description")
        if description is not None and not isinstance(description, str):
            errors.append("Field 'description' must be a string or null.")

        # 6. visibility
        visibility = record_dict.get("visibility")
        if not isinstance(visibility, str) or visibility not in cls.VALID_VISIBILITIES:
            vis_list = sorted(cls.VALID_VISIBILITIES)
            errors.append(
                f"Field 'visibility' must be one of {vis_list}, got '{visibility}'."
            )

        # 7. default_branch
        default_branch = record_dict.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch.strip():
            errors.append("Field 'default_branch' must be a non-empty string.")

        # 8. language (nullable string)
        language = record_dict.get("language")
        if language is not None and not isinstance(language, str):
            errors.append("Field 'language' must be a string or null.")

        # 9. Booleans
        for bool_field in ("is_fork", "is_archived", "is_disabled"):
            val = record_dict.get(bool_field)
            if not isinstance(val, bool):
                errors.append(f"Field '{bool_field}' must be a boolean.")

        # 10. Non-negative metrics
        metric_fields = (
            "stars_count",
            "forks_count",
            "open_issues_count",
            "subscribers_count",
            "size_kb",
        )
        for m_field in metric_fields:
            val = record_dict.get(m_field)
            if val is None or isinstance(val, bool) or not isinstance(val, int):
                errors.append(f"Field '{m_field}' must be an integer.")
            elif val < 0:
                errors.append(f"Field '{m_field}' cannot be negative, got {val}.")

        # 11. html_url
        html_url = record_dict.get("html_url")
        if not isinstance(html_url, str) or not html_url.strip():
            errors.append("Field 'html_url' must be a non-empty string.")

        # 12. Timestamps
        created_at = cls._parse_timestamp(
            record_dict.get("created_at"), "created_at", errors
        )
        updated_at = cls._parse_timestamp(
            record_dict.get("updated_at"), "updated_at", errors
        )
        pushed_at = (
            cls._parse_timestamp(record_dict.get("pushed_at"), "pushed_at", errors)
            if record_dict.get("pushed_at") is not None
            else None
        )
        extracted_at = cls._parse_timestamp(
            record_dict.get("extracted_at"), "extracted_at", errors
        )

        if errors:
            err_msg = "; ".join(errors)
            raise ContractValidationError(
                f"Repository contract validation failed with {len(errors)} errors: "
                f"{err_msg}",
                details=errors,
            )

        return RepositoryRecord(
            repository_id=repo_id,  # type: ignore[arg-type]
            repository_name=repo_name.strip(),  # type: ignore[union-attr]
            full_name=full_name.strip(),  # type: ignore[union-attr]
            owner_login=owner_login.strip(),  # type: ignore[union-attr]
            description=description.strip() if isinstance(description, str) else None,
            visibility=visibility,  # type: ignore[arg-type]
            default_branch=default_branch.strip(),  # type: ignore[union-attr]
            language=language.strip() if isinstance(language, str) else None,
            is_fork=record_dict["is_fork"],
            is_archived=record_dict["is_archived"],
            is_disabled=record_dict["is_disabled"],
            created_at=created_at,  # type: ignore[arg-type]
            updated_at=updated_at,  # type: ignore[arg-type]
            pushed_at=pushed_at,
            stars_count=record_dict["stars_count"],
            forks_count=record_dict["forks_count"],
            open_issues_count=record_dict["open_issues_count"],
            subscribers_count=record_dict["subscribers_count"],
            size_kb=record_dict["size_kb"],
            html_url=html_url.strip(),  # type: ignore[union-attr]
            extracted_at=extracted_at,  # type: ignore[arg-type]
        )

    @classmethod
    def _parse_timestamp(
        cls, val: Any, field_name: str, errors: list[str]
    ) -> datetime | None:
        """Ensure value is a timezone-aware UTC datetime."""
        if val is None:
            errors.append(f"Field '{field_name}' must not be null.")
            return None

        if isinstance(val, datetime):
            if val.tzinfo is None or val.utcoffset() is None:
                errors.append(f"Field '{field_name}' must be timezone-aware.")
                return None
            return val.astimezone(UTC)

        if isinstance(val, str):
            val_clean = val.strip()
            if not val_clean:
                errors.append(
                    f"Field '{field_name}' must be a non-empty ISO 8601 string."
                )
                return None
            if val_clean.endswith("Z"):
                val_clean = f"{val_clean[:-1]}+00:00"
            try:
                dt = datetime.fromisoformat(val_clean)
                if dt.tzinfo is None or dt.utcoffset() is None:
                    errors.append(f"Field '{field_name}' must include timezone offset.")
                    return None
                return dt.astimezone(UTC)
            except ValueError:
                errors.append(
                    f"Field '{field_name}' contains an invalid datetime string '{val}'."
                )
                return None

        errors.append(
            f"Field '{field_name}' must be a datetime or ISO 8601 string, "
            f"got {type(val).__name__}."
        )
        return None
