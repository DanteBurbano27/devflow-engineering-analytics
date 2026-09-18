"""Comprehensive data quality rules for repository metadata records."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from analytics.contracts.repository import RepositoryRecord
from analytics.quality.models import QualityIssue, QualitySeverity
from ingestion.github.repository_metadata import RepositoryMetadata


def _extract_dict(item: Any) -> dict[str, Any]:
    """Safely convert supported record types to a standard dictionary."""
    if isinstance(item, RepositoryRecord):
        return item.to_dict()
    if isinstance(item, RepositoryMetadata):
        return item.to_record()
    if isinstance(item, Mapping):
        return dict(item)
    return {}


def _get_identifier(data: dict[str, Any]) -> str | int | None:
    """Extract best available record identifier for logging issues."""
    return data.get("full_name") or data.get("repository_id")


def _coerce_datetime(val: Any) -> datetime | None:
    """Coerce string or datetime to timezone-aware UTC datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return None
        return val.astimezone(UTC)
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            return None
        if val_str.endswith("Z"):
            val_str = f"{val_str[:-1]}+00:00"
        try:
            dt = datetime.fromisoformat(val_str)
            if dt.tzinfo is None:
                return None
            return dt.astimezone(UTC)
        except ValueError:
            return None
    return None


class QualityRule(ABC):
    """Abstract base class for record-level data quality validation rules."""

    rule_id: str
    rule_name: str
    severity: QualitySeverity

    @abstractmethod
    def evaluate(self, record: Any) -> list[QualityIssue]:
        """Evaluate rule against a single record, returning list of issues found."""
        ...


class BatchQualityRule(ABC):
    """Abstract base class for batch data quality rules (e.g. uniqueness)."""

    rule_id: str
    rule_name: str
    severity: QualitySeverity

    @abstractmethod
    def evaluate_batch(self, records: list[Any]) -> list[QualityIssue]:
        """Evaluate rule across an entire batch of records."""
        ...


# =====================================================================
# RECORD-LEVEL RULES
# =====================================================================


class ValidRepositoryIdRule(QualityRule):
    """Ensure repository_id is a strictly positive integer."""

    rule_id = "DQ-ID-001"
    rule_name = "Valid Positive Repository ID"
    severity = QualitySeverity.ERROR

    def evaluate(self, record: Any) -> list[QualityIssue]:
        data = _extract_dict(record)
        repo_id = data.get("repository_id")
        ident = _get_identifier(data)

        if repo_id is None or isinstance(repo_id, bool) or not isinstance(repo_id, int):
            return [
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="repository_id",
                    message="Field 'repository_id' is missing or not an integer.",
                    record_identifier=ident,
                    actual_value=repo_id,
                )
            ]

        if repo_id <= 0:
            return [
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="repository_id",
                    message=f"Field 'repository_id' must be positive, got {repo_id}.",
                    record_identifier=ident,
                    actual_value=repo_id,
                )
            ]

        return []


class NonEmptyFullNameRule(QualityRule):
    """Ensure full_name is present and non-empty."""

    rule_id = "DQ-NAME-001"
    rule_name = "Non-Empty Full Name"
    severity = QualitySeverity.ERROR

    def evaluate(self, record: Any) -> list[QualityIssue]:
        data = _extract_dict(record)
        name = data.get("full_name")
        ident = _get_identifier(data)

        if not isinstance(name, str) or not name.strip():
            return [
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="full_name",
                    message="Field 'full_name' is missing or empty.",
                    record_identifier=ident,
                    actual_value=name,
                )
            ]
        return []


class FullNamePatternRule(QualityRule):
    """Ensure full_name matches standard 'owner/repo' format."""

    rule_id = "DQ-NAME-002"
    rule_name = "Full Name Format Pattern"
    severity = QualitySeverity.ERROR

    def evaluate(self, record: Any) -> list[QualityIssue]:
        data = _extract_dict(record)
        name = data.get("full_name")
        ident = _get_identifier(data)

        if isinstance(name, str) and name.strip():
            parts = name.strip().split("/")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                return [
                    QualityIssue(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        severity=self.severity,
                        field="full_name",
                        message=(
                            f"Field 'full_name' must follow 'owner/repo' pattern, "
                            f"got '{name}'."
                        ),
                        record_identifier=ident,
                        actual_value=name,
                    )
                ]
        return []


class NonEmptyOwnerRule(QualityRule):
    """Ensure owner_login is present and non-empty."""

    rule_id = "DQ-OWNER-001"
    rule_name = "Non-Empty Owner Login"
    severity = QualitySeverity.ERROR

    def evaluate(self, record: Any) -> list[QualityIssue]:
        data = _extract_dict(record)
        owner = data.get("owner_login")
        ident = _get_identifier(data)

        if not isinstance(owner, str) or not owner.strip():
            return [
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="owner_login",
                    message="Field 'owner_login' is missing or empty.",
                    record_identifier=ident,
                    actual_value=owner,
                )
            ]
        return []


class OwnerFullNameConsistencyRule(QualityRule):
    """Ensure owner_login matches the prefix of full_name."""

    rule_id = "DQ-CONS-001"
    rule_name = "Owner and Full Name Consistency"
    severity = QualitySeverity.ERROR

    def evaluate(self, record: Any) -> list[QualityIssue]:
        data = _extract_dict(record)
        owner = data.get("owner_login")
        full_name = data.get("full_name")
        ident = _get_identifier(data)

        if (
            isinstance(owner, str)
            and owner.strip()
            and isinstance(full_name, str)
            and full_name.strip()
        ):
            expected_prefix = f"{owner.strip()}/"
            if not full_name.strip().startswith(expected_prefix):
                return [
                    QualityIssue(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        severity=self.severity,
                        field="full_name",
                        message=(
                            f"Identity mismatch: full_name '{full_name}' "
                            f"does not start with owner '{owner}'."
                        ),
                        record_identifier=ident,
                        actual_value=f"owner={owner}, full_name={full_name}",
                    )
                ]
        return []


class NonNegativeMetricsRule(QualityRule):
    """Ensure numeric counter metrics are non-negative integers."""

    rule_id = "DQ-METRIC-001"
    rule_name = "Non-Negative Numeric Metrics"
    severity = QualitySeverity.ERROR

    FIELDS: tuple[str, ...] = (
        "stars_count",
        "forks_count",
        "open_issues_count",
        "subscribers_count",
        "size_kb",
    )

    def evaluate(self, record: Any) -> list[QualityIssue]:
        data = _extract_dict(record)
        ident = _get_identifier(data)
        issues: list[QualityIssue] = []

        for field in self.FIELDS:
            val = data.get(field)
            if val is None or isinstance(val, bool) or not isinstance(val, int):
                issues.append(
                    QualityIssue(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        severity=self.severity,
                        field=field,
                        message=(
                            f"Field '{field}' must be an integer, "
                            f"got {type(val).__name__}."
                        ),
                        record_identifier=ident,
                        actual_value=val,
                    )
                )
            elif val < 0:
                issues.append(
                    QualityIssue(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        severity=self.severity,
                        field=field,
                        message=f"Field '{field}' cannot be negative, got {val}.",
                        record_identifier=ident,
                        actual_value=val,
                    )
                )

        return issues


class ExpectedVisibilityRule(QualityRule):
    """Ensure repository visibility belongs to allowed set."""

    rule_id = "DQ-VIS-001"
    rule_name = "Expected Visibility Domain"
    severity = QualitySeverity.ERROR
    ALLOWED: frozenset[str] = frozenset({"public", "private", "internal"})

    def evaluate(self, record: Any) -> list[QualityIssue]:
        data = _extract_dict(record)
        vis = data.get("visibility")
        ident = _get_identifier(data)

        if not isinstance(vis, str) or vis not in self.ALLOWED:
            allowed_str = sorted(self.ALLOWED)
            return [
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="visibility",
                    message=f"Visibility must be one of {allowed_str}, got '{vis}'.",
                    record_identifier=ident,
                    actual_value=vis,
                )
            ]
        return []


class ExtractedAtPresentRule(QualityRule):
    """Ensure extracted_at ingestion timestamp is present and valid."""

    rule_id = "DQ-TIME-001"
    rule_name = "Extracted At Timestamp Presence"
    severity = QualitySeverity.ERROR

    def evaluate(self, record: Any) -> list[QualityIssue]:
        data = _extract_dict(record)
        ident = _get_identifier(data)
        val = data.get("extracted_at")

        if val is None:
            return [
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="extracted_at",
                    message="Field 'extracted_at' is required for lineage and missing.",
                    record_identifier=ident,
                    actual_value=None,
                )
            ]

        dt = _coerce_datetime(val)
        if dt is None:
            return [
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="extracted_at",
                    message=(
                        f"Field 'extracted_at' contains invalid or naive "
                        f"timestamp '{val}'."
                    ),
                    record_identifier=ident,
                    actual_value=val,
                )
            ]

        return []


class TemporalConsistencyRule(QualityRule):
    """Ensure consistency between created_at, updated_at, and extracted_at."""

    rule_id = "DQ-TIME-002"
    rule_name = "Chronological Order Consistency"
    severity = QualitySeverity.ERROR

    def evaluate(self, record: Any) -> list[QualityIssue]:
        data = _extract_dict(record)
        ident = _get_identifier(data)
        issues: list[QualityIssue] = []

        created_dt = _coerce_datetime(data.get("created_at"))
        updated_dt = _coerce_datetime(data.get("updated_at"))
        extracted_dt = _coerce_datetime(data.get("extracted_at"))

        if created_dt is None:
            issues.append(
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="created_at",
                    message=(
                        "Field 'created_at' must be a valid timezone-aware timestamp."
                    ),
                    record_identifier=ident,
                    actual_value=data.get("created_at"),
                )
            )

        if updated_dt is None:
            issues.append(
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="updated_at",
                    message=(
                        "Field 'updated_at' must be a valid timezone-aware timestamp."
                    ),
                    record_identifier=ident,
                    actual_value=data.get("updated_at"),
                )
            )

        if created_dt and updated_dt and updated_dt < created_dt:
            issues.append(
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="updated_at",
                    message=(
                        f"Temporal anomaly: updated_at ({updated_dt.isoformat()}) "
                        f"is earlier than created_at ({created_dt.isoformat()})."
                    ),
                    record_identifier=ident,
                    actual_value=f"created={created_dt}, updated={updated_dt}",
                )
            )

        if created_dt and extracted_dt and created_dt > extracted_dt:
            issues.append(
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="created_at",
                    message=(
                        f"Temporal anomaly: created_at ({created_dt.isoformat()}) "
                        f"is in the future relative to extracted_at "
                        f"({extracted_dt.isoformat()})."
                    ),
                    record_identifier=ident,
                    actual_value=f"created={created_dt}, extracted={extracted_dt}",
                )
            )

        return issues


class PushedAtConsistencyRule(QualityRule):
    """Warn when pushed_at is temporally earlier than repository creation."""

    rule_id = "DQ-TIME-003"
    rule_name = "Pushed At Timestamp Plausibility"
    severity = QualitySeverity.WARNING

    def evaluate(self, record: Any) -> list[QualityIssue]:
        data = _extract_dict(record)
        ident = _get_identifier(data)
        pushed_raw = data.get("pushed_at")

        if pushed_raw is None:
            return []

        pushed_dt = _coerce_datetime(pushed_raw)
        created_dt = _coerce_datetime(data.get("created_at"))

        if pushed_dt is None:
            return [
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="pushed_at",
                    message=(
                        f"Optional field 'pushed_at' has unparseable "
                        f"timestamp '{pushed_raw}'."
                    ),
                    record_identifier=ident,
                    actual_value=pushed_raw,
                )
            ]

        if created_dt and pushed_dt < created_dt:
            return [
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="pushed_at",
                    message=(
                        f"Temporal warning: pushed_at ({pushed_dt.isoformat()}) "
                        f"precedes created_at ({created_dt.isoformat()})."
                    ),
                    record_identifier=ident,
                    actual_value=f"created={created_dt}, pushed={pushed_dt}",
                )
            ]

        return []


class HtmlUrlValidityRule(QualityRule):
    """Warn when html_url is not a plausible web URL."""

    rule_id = "DQ-URL-001"
    rule_name = "Valid HTML URL Scheme"
    severity = QualitySeverity.WARNING

    def evaluate(self, record: Any) -> list[QualityIssue]:
        data = _extract_dict(record)
        url = data.get("html_url")
        ident = _get_identifier(data)

        if not isinstance(url, str) or not (
            url.startswith("http://") or url.startswith("https://")
        ):
            return [
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="html_url",
                    message=(
                        f"Field 'html_url' should start with http:// or https://, "
                        f"got '{url}'."
                    ),
                    record_identifier=ident,
                    actual_value=url,
                )
            ]
        return []


class NonEmptyRepositoryNameRule(QualityRule):
    """Ensure repository_name is present, non-empty, and matches full_name."""

    rule_id = "DQ-NAME-003"
    rule_name = "Non-Empty Repository Name"
    severity = QualitySeverity.ERROR

    def evaluate(self, record: Any) -> list[QualityIssue]:
        data = _extract_dict(record)
        name = data.get("repository_name")
        full_name = data.get("full_name")
        ident = _get_identifier(data)

        if not isinstance(name, str) or not name.strip():
            return [
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="repository_name",
                    message="Field 'repository_name' is missing or empty.",
                    record_identifier=ident,
                    actual_value=name,
                )
            ]

        if isinstance(full_name, str) and "/" in full_name:
            expected_suffix = f"/{name.strip()}"
            if not full_name.strip().endswith(expected_suffix):
                return [
                    QualityIssue(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        severity=self.severity,
                        field="repository_name",
                        message=(
                            f"Identity mismatch: full_name '{full_name}' "
                            f"does not end with repository_name '{name}'."
                        ),
                        record_identifier=ident,
                        actual_value=f"name={name}, full_name={full_name}",
                    )
                ]

        return []


class NonEmptyDefaultBranchRule(QualityRule):
    """Ensure default_branch is a non-empty valid string."""

    rule_id = "DQ-BRANCH-001"
    rule_name = "Non-Empty Default Branch"
    severity = QualitySeverity.ERROR

    def evaluate(self, record: Any) -> list[QualityIssue]:
        data = _extract_dict(record)
        branch = data.get("default_branch")
        ident = _get_identifier(data)

        if not isinstance(branch, str) or not branch.strip():
            return [
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="default_branch",
                    message="Field 'default_branch' is missing or empty.",
                    record_identifier=ident,
                    actual_value=branch,
                )
            ]
        return []


class RequiredFieldsNullabilityRule(QualityRule):
    """Ensure non-nullable required contract fields are present and not None."""

    rule_id = "DQ-NULL-001"
    rule_name = "Non-Nullable Fields Nullability Check"
    severity = QualitySeverity.ERROR

    REQUIRED_FIELDS: tuple[str, ...] = (
        "repository_id",
        "repository_name",
        "full_name",
        "owner_login",
        "visibility",
        "default_branch",
        "is_fork",
        "is_archived",
        "is_disabled",
        "created_at",
        "updated_at",
        "stars_count",
        "forks_count",
        "open_issues_count",
        "subscribers_count",
        "size_kb",
        "html_url",
        "extracted_at",
    )

    def evaluate(self, record: Any) -> list[QualityIssue]:
        data = _extract_dict(record)
        ident = _get_identifier(data)
        issues: list[QualityIssue] = []

        for field in self.REQUIRED_FIELDS:
            if field not in data or data[field] is None:
                issues.append(
                    QualityIssue(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        severity=self.severity,
                        field=field,
                        message=(
                            f"Required non-nullable field '{field}' is missing or null."
                        ),
                        record_identifier=ident,
                        actual_value=None,
                    )
                )

        return issues


class UniqueRepositoryIdRule(BatchQualityRule):
    """Ensure repository_id is unique across a batch."""

    rule_id = "DQ-DUP-001"
    rule_name = "Unique Repository ID Across Batch"
    severity = QualitySeverity.ERROR

    def evaluate_batch(self, records: list[Any]) -> list[QualityIssue]:
        counts: Counter[int] = Counter()
        for r in records:
            data = _extract_dict(r)
            rid = data.get("repository_id")
            if isinstance(rid, int) and not isinstance(rid, bool):
                counts[rid] += 1

        duplicates = {rid: c for rid, c in counts.items() if c > 1}
        issues: list[QualityIssue] = []
        for rid, c in duplicates.items():
            issues.append(
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="repository_id",
                    message=f"Duplicate repository_id {rid} found {c} times in batch.",
                    record_identifier=rid,
                    actual_value=c,
                )
            )
        return issues


class UniqueFullNameRule(BatchQualityRule):
    """Ensure full_name is unique across a batch."""

    rule_id = "DQ-DUP-002"
    rule_name = "Unique Full Name Across Batch"
    severity = QualitySeverity.ERROR

    def evaluate_batch(self, records: list[Any]) -> list[QualityIssue]:
        counts: Counter[str] = Counter()
        for r in records:
            data = _extract_dict(r)
            name = data.get("full_name")
            if isinstance(name, str) and name.strip():
                counts[name.strip().lower()] += 1

        duplicates = {name: c for name, c in counts.items() if c > 1}
        issues: list[QualityIssue] = []
        for name, c in duplicates.items():
            issues.append(
                QualityIssue(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    field="full_name",
                    message=f"Duplicate full_name '{name}' found {c} times in batch.",
                    record_identifier=name,
                    actual_value=c,
                )
            )
        return issues
