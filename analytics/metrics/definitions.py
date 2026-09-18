"""Definitions and schemas for derived repository metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class ActivityStatus(StrEnum):
    """Categorization of repository freshness and maintenance status."""

    ACTIVE = "ACTIVE"
    STALE = "STALE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"
    DISABLED = "DISABLED"


class RecencyBucket(StrEnum):
    """Standardized time window categorizing the last commit push."""

    LAST_7_DAYS = "LAST_7_DAYS"
    LAST_30_DAYS = "LAST_30_DAYS"
    LAST_90_DAYS = "LAST_90_DAYS"
    LAST_180_DAYS = "LAST_180_DAYS"
    OVER_180_DAYS = "OVER_180_DAYS"
    NEVER_PUSHED = "NEVER_PUSHED"


class SizeCategory(StrEnum):
    """Repository size classifications based on KB."""

    EMPTY = "EMPTY"  # 0 KB
    MICRO = "MICRO"  # 1 - 100 KB
    SMALL = "SMALL"  # 101 - 10,000 KB (~10 MB)
    MEDIUM = "MEDIUM"  # 10,001 - 100,000 KB (~100 MB)
    LARGE = "LARGE"  # > 100,000 KB


@dataclass(frozen=True, slots=True)
class RepositoryMetrics:
    """Analytical metrics derived from a validated repository record."""

    repository_id: int
    repository_name: str
    full_name: str
    owner_login: str
    language: str | None
    visibility: str
    is_fork: bool
    is_archived: bool
    is_disabled: bool

    # Raw counts
    stars_count: int
    forks_count: int
    open_issues_count: int
    subscribers_count: int
    size_kb: int

    # Temporal & Activity metrics
    days_since_last_push: int | None
    days_since_creation: int
    repository_age_days: int
    days_between_creation_and_last_push: int | None
    activity_status: ActivityStatus
    recency_bucket: RecencyBucket
    is_active: bool

    # Engagement & Technical Ratios
    fork_to_star_ratio: float
    issue_to_star_ratio: float
    star_to_fork_ratio: float
    issue_to_fork_ratio: float
    issue_density_per_mb: float
    community_interest_score: float
    size_category: SizeCategory

    # Metadata
    reference_time: datetime
    calculated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Serialize metrics to dictionary."""
        data = asdict(self)
        data["activity_status"] = self.activity_status.value
        data["recency_bucket"] = self.recency_bucket.value
        data["size_category"] = self.size_category.value
        data["reference_time"] = self.reference_time.isoformat()
        data["calculated_at"] = self.calculated_at.isoformat()
        return data
