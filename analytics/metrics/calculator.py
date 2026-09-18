"""Deterministic calculator for repository derived metrics."""

from __future__ import annotations

from datetime import UTC, datetime

from analytics.contracts.repository import RepositoryRecord
from analytics.metrics.definitions import (
    ActivityStatus,
    RecencyBucket,
    RepositoryMetrics,
    SizeCategory,
)


class RepositoryMetricCalculator:
    """Calculates standardized, technically defensible metrics for repositories."""

    ACTIVE_THRESHOLD_DAYS: int = 90
    STALE_THRESHOLD_DAYS: int = 180

    @classmethod
    def calculate(
        cls,
        record: RepositoryRecord,
        *,
        reference_time: datetime | None = None,
    ) -> RepositoryMetrics:
        """Derive all analytical metrics for a validated repository record.

        Parameters
        ----------
        record:
            Validated RepositoryRecord.
        reference_time:
            Evaluation point. Defaults to record.extracted_at to guarantee determinism.
        """
        ref_time = (
            reference_time.astimezone(UTC)
            if reference_time is not None
            else record.extracted_at
        )

        # 1. Temporal spans
        days_since_creation = max(0, (ref_time - record.created_at).days)
        repository_age_days = days_since_creation

        if record.pushed_at is not None:
            days_since_last_push: int | None = max(
                0, (ref_time - record.pushed_at).days
            )
            days_between_creation_and_last_push: int | None = max(
                0, (record.pushed_at - record.created_at).days
            )
        else:
            days_since_last_push = None
            days_between_creation_and_last_push = None

        # 2. Activity status and recency bucket
        activity_status = cls._determine_activity_status(
            is_disabled=record.is_disabled,
            is_archived=record.is_archived,
            days_since_last_push=days_since_last_push,
        )
        recency_bucket = cls._determine_recency_bucket(days_since_last_push)
        is_active = activity_status == ActivityStatus.ACTIVE

        # 3. Ratios (zero-division safe)
        fork_to_star_ratio = (
            round(record.forks_count / record.stars_count, 4)
            if record.stars_count > 0
            else 0.0
        )
        issue_to_star_ratio = (
            round(record.open_issues_count / record.stars_count, 4)
            if record.stars_count > 0
            else 0.0
        )
        star_to_fork_ratio = (
            round(record.stars_count / record.forks_count, 4)
            if record.forks_count > 0
            else 0.0
        )
        issue_to_fork_ratio = (
            round(record.open_issues_count / record.forks_count, 4)
            if record.forks_count > 0
            else 0.0
        )
        size_mb = record.size_kb / 1024.0
        issue_density_per_mb = (
            round(record.open_issues_count / size_mb, 4) if size_mb > 0 else 0.0
        )

        # 4. Popularity / interest score
        # Stars (1.0 weight), Forks indicate active extension (2.0 weight),
        # Watchers/Subscribers indicate ongoing attention (1.5 weight).
        community_interest_score = round(
            (record.stars_count * 1.0)
            + (record.forks_count * 2.0)
            + (record.subscribers_count * 1.5),
            2,
        )

        # 5. Size category
        size_category = cls._classify_size(record.size_kb)

        return RepositoryMetrics(
            repository_id=record.repository_id,
            repository_name=record.repository_name,
            full_name=record.full_name,
            owner_login=record.owner_login,
            language=record.language,
            visibility=record.visibility,
            is_fork=record.is_fork,
            is_archived=record.is_archived,
            is_disabled=record.is_disabled,
            stars_count=record.stars_count,
            forks_count=record.forks_count,
            open_issues_count=record.open_issues_count,
            subscribers_count=record.subscribers_count,
            size_kb=record.size_kb,
            days_since_last_push=days_since_last_push,
            days_since_creation=days_since_creation,
            repository_age_days=repository_age_days,
            days_between_creation_and_last_push=days_between_creation_and_last_push,
            activity_status=activity_status,
            recency_bucket=recency_bucket,
            is_active=is_active,
            fork_to_star_ratio=fork_to_star_ratio,
            issue_to_star_ratio=issue_to_star_ratio,
            star_to_fork_ratio=star_to_fork_ratio,
            issue_to_fork_ratio=issue_to_fork_ratio,
            issue_density_per_mb=issue_density_per_mb,
            community_interest_score=community_interest_score,
            size_category=size_category,
            reference_time=ref_time,
            calculated_at=datetime.now(UTC),
        )

    @classmethod
    def _determine_activity_status(
        cls,
        *,
        is_disabled: bool,
        is_archived: bool,
        days_since_last_push: int | None,
    ) -> ActivityStatus:
        """Map repository flags and recency into operational status."""
        if is_disabled:
            return ActivityStatus.DISABLED

        if is_archived:
            return ActivityStatus.ARCHIVED

        if days_since_last_push is None:
            return ActivityStatus.INACTIVE

        if days_since_last_push <= cls.ACTIVE_THRESHOLD_DAYS:
            return ActivityStatus.ACTIVE

        if days_since_last_push <= cls.STALE_THRESHOLD_DAYS:
            return ActivityStatus.STALE

        return ActivityStatus.INACTIVE

    @classmethod
    def _determine_recency_bucket(
        cls, days_since_last_push: int | None
    ) -> RecencyBucket:
        """Categorize days since last push into standardized time windows."""
        if days_since_last_push is None:
            return RecencyBucket.NEVER_PUSHED
        if days_since_last_push <= 7:
            return RecencyBucket.LAST_7_DAYS
        if days_since_last_push <= 30:
            return RecencyBucket.LAST_30_DAYS
        if days_since_last_push <= 90:
            return RecencyBucket.LAST_90_DAYS
        if days_since_last_push <= 180:
            return RecencyBucket.LAST_180_DAYS
        return RecencyBucket.OVER_180_DAYS

    @classmethod
    def _classify_size(cls, size_kb: int) -> SizeCategory:
        """Classify repository size into human-interpretable categories."""
        if size_kb == 0:
            return SizeCategory.EMPTY
        if size_kb <= 100:
            return SizeCategory.MICRO
        if size_kb <= 10_000:
            return SizeCategory.SMALL
        if size_kb <= 100_000:
            return SizeCategory.MEDIUM
        return SizeCategory.LARGE
