"""Tests for derived repository metric computations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from analytics.contracts.repository import RepositoryRecord
from analytics.metrics.calculator import RepositoryMetricCalculator
from analytics.metrics.definitions import ActivityStatus, SizeCategory


def make_record(
    *,
    repository_id: int = 101,
    created_at: datetime,
    pushed_at: datetime | None,
    extracted_at: datetime,
    stars_count: int = 100,
    forks_count: int = 20,
    open_issues_count: int = 5,
    subscribers_count: int = 15,
    size_kb: int = 5000,
    is_archived: bool = False,
    is_disabled: bool = False,
    language: str | None = "Python",
) -> RepositoryRecord:
    """Create test RepositoryRecord instance."""
    return RepositoryRecord(
        repository_id=repository_id,
        repository_name="test-repo",
        full_name="org/test-repo",
        owner_login="org",
        description="A test repository",
        visibility="public",
        default_branch="main",
        language=language,
        is_fork=False,
        is_archived=is_archived,
        is_disabled=is_disabled,
        created_at=created_at,
        updated_at=pushed_at or created_at,
        pushed_at=pushed_at,
        stars_count=stars_count,
        forks_count=forks_count,
        open_issues_count=open_issues_count,
        subscribers_count=subscribers_count,
        size_kb=size_kb,
        html_url="https://github.com/org/test-repo",
        extracted_at=extracted_at,
    )


def test_calculate_active_status() -> None:
    """Repository pushed within 90 days must be ACTIVE."""
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    record = make_record(
        created_at=now - timedelta(days=200),
        pushed_at=now - timedelta(days=30),
        extracted_at=now,
    )
    metrics = RepositoryMetricCalculator.calculate(record, reference_time=now)

    assert metrics.activity_status == ActivityStatus.ACTIVE
    assert metrics.is_active is True
    assert metrics.days_since_last_push == 30
    assert metrics.days_since_creation == 200
    assert metrics.days_between_creation_and_last_push == 170


def test_calculate_stale_status() -> None:
    """Repository pushed between 91 and 180 days ago must be STALE."""
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    record = make_record(
        created_at=now - timedelta(days=300),
        pushed_at=now - timedelta(days=120),
        extracted_at=now,
    )
    metrics = RepositoryMetricCalculator.calculate(record, reference_time=now)

    assert metrics.activity_status == ActivityStatus.STALE
    assert metrics.is_active is False
    assert metrics.days_since_last_push == 120


def test_calculate_inactive_status() -> None:
    """Repository pushed > 180 days ago must be INACTIVE."""
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    record = make_record(
        created_at=now - timedelta(days=500),
        pushed_at=now - timedelta(days=250),
        extracted_at=now,
    )
    metrics = RepositoryMetricCalculator.calculate(record, reference_time=now)

    assert metrics.activity_status == ActivityStatus.INACTIVE
    assert metrics.is_active is False
    assert metrics.days_since_last_push == 250


def test_calculate_archived_and_disabled_statuses() -> None:
    """Archived and disabled flags must override recency calculation."""
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)

    # Archived repo with recent push
    archived_record = make_record(
        created_at=now - timedelta(days=100),
        pushed_at=now - timedelta(days=10),
        extracted_at=now,
        is_archived=True,
    )
    arch_metrics = RepositoryMetricCalculator.calculate(
        archived_record, reference_time=now
    )
    assert arch_metrics.activity_status == ActivityStatus.ARCHIVED
    assert arch_metrics.is_active is False

    # Disabled repo
    disabled_record = make_record(
        created_at=now - timedelta(days=100),
        pushed_at=now - timedelta(days=10),
        extracted_at=now,
        is_disabled=True,
    )
    dis_metrics = RepositoryMetricCalculator.calculate(
        disabled_record, reference_time=now
    )
    assert dis_metrics.activity_status == ActivityStatus.DISABLED
    assert dis_metrics.is_active is False


def test_calculate_without_pushed_at() -> None:
    """Repositories with null pushed_at must handle None gracefully."""
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    record = make_record(
        created_at=now - timedelta(days=50),
        pushed_at=None,
        extracted_at=now,
    )
    metrics = RepositoryMetricCalculator.calculate(record, reference_time=now)

    assert metrics.activity_status == ActivityStatus.INACTIVE
    assert metrics.days_since_last_push is None
    assert metrics.days_between_creation_and_last_push is None
    assert metrics.days_since_creation == 50


def test_technical_ratios_and_zero_division_safety() -> None:
    """Ratios must compute correctly and safely return 0.0 when denominator is zero."""
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)

    # Zero stars & zero forks
    zero_record = make_record(
        created_at=now - timedelta(days=10),
        pushed_at=now - timedelta(days=1),
        extracted_at=now,
        stars_count=0,
        forks_count=0,
        open_issues_count=3,
        subscribers_count=2,
    )
    zero_metrics = RepositoryMetricCalculator.calculate(zero_record, reference_time=now)

    assert zero_metrics.fork_to_star_ratio == 0.0
    assert zero_metrics.issue_to_star_ratio == 0.0
    assert zero_metrics.star_to_fork_ratio == 0.0
    assert zero_metrics.community_interest_score == 3.0  # 2 subscribers * 1.5

    # Populated counts
    normal_record = make_record(
        created_at=now - timedelta(days=100),
        pushed_at=now - timedelta(days=5),
        extracted_at=now,
        stars_count=200,
        forks_count=50,
        open_issues_count=10,
        subscribers_count=40,
    )
    m = RepositoryMetricCalculator.calculate(normal_record, reference_time=now)
    assert m.fork_to_star_ratio == 0.25
    assert m.issue_to_star_ratio == 0.05
    assert m.star_to_fork_ratio == 4.0
    # 200*1 + 50*2 + 40*1.5 = 200 + 100 + 60 = 360.0
    assert m.community_interest_score == 360.0


def test_size_classification_categories() -> None:
    """Size categories must match defined KB thresholds."""
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)

    rec_empty = make_record(created_at=now, pushed_at=now, extracted_at=now, size_kb=0)
    assert (
        RepositoryMetricCalculator.calculate(rec_empty).size_category
        == SizeCategory.EMPTY
    )

    rec_micro = make_record(created_at=now, pushed_at=now, extracted_at=now, size_kb=50)
    assert (
        RepositoryMetricCalculator.calculate(rec_micro).size_category
        == SizeCategory.MICRO
    )

    rec_small = make_record(
        created_at=now, pushed_at=now, extracted_at=now, size_kb=5000
    )
    assert (
        RepositoryMetricCalculator.calculate(rec_small).size_category
        == SizeCategory.SMALL
    )

    rec_med = make_record(
        created_at=now, pushed_at=now, extracted_at=now, size_kb=50000
    )
    assert (
        RepositoryMetricCalculator.calculate(rec_med).size_category
        == SizeCategory.MEDIUM
    )

    rec_large = make_record(
        created_at=now, pushed_at=now, extracted_at=now, size_kb=500000
    )
    assert (
        RepositoryMetricCalculator.calculate(rec_large).size_category
        == SizeCategory.LARGE
    )


def test_metrics_serialization() -> None:
    """RepositoryMetrics.to_dict() must format all values as primitives."""
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    record = make_record(
        created_at=now - timedelta(days=20),
        pushed_at=now - timedelta(days=2),
        extracted_at=now,
    )
    metrics = RepositoryMetricCalculator.calculate(record)
    metrics_dict = metrics.to_dict()

    assert metrics_dict["repository_id"] == 101
    assert metrics_dict["activity_status"] == "ACTIVE"
    assert metrics_dict["recency_bucket"] == "LAST_7_DAYS"
    assert metrics_dict["size_category"] == "SMALL"
    assert "repository_age_days" in metrics_dict
    assert "issue_to_fork_ratio" in metrics_dict
    assert "issue_density_per_mb" in metrics_dict
    assert isinstance(metrics_dict["reference_time"], str)
    assert isinstance(metrics_dict["calculated_at"], str)


def test_recency_buckets() -> None:
    """All recency buckets must be assigned correctly."""
    from analytics.metrics.definitions import RecencyBucket

    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)

    # NEVER_PUSHED
    r_never = make_record(created_at=now, pushed_at=None, extracted_at=now)
    assert (
        RepositoryMetricCalculator.calculate(r_never, reference_time=now).recency_bucket
        == RecencyBucket.NEVER_PUSHED
    )

    # LAST_7_DAYS
    r_7 = make_record(
        created_at=now - timedelta(days=10),
        pushed_at=now - timedelta(days=5),
        extracted_at=now,
    )
    assert (
        RepositoryMetricCalculator.calculate(r_7, reference_time=now).recency_bucket
        == RecencyBucket.LAST_7_DAYS
    )

    # LAST_30_DAYS
    r_30 = make_record(
        created_at=now - timedelta(days=50),
        pushed_at=now - timedelta(days=20),
        extracted_at=now,
    )
    assert (
        RepositoryMetricCalculator.calculate(r_30, reference_time=now).recency_bucket
        == RecencyBucket.LAST_30_DAYS
    )

    # LAST_90_DAYS
    r_90 = make_record(
        created_at=now - timedelta(days=100),
        pushed_at=now - timedelta(days=60),
        extracted_at=now,
    )
    assert (
        RepositoryMetricCalculator.calculate(r_90, reference_time=now).recency_bucket
        == RecencyBucket.LAST_90_DAYS
    )

    # LAST_180_DAYS
    r_180 = make_record(
        created_at=now - timedelta(days=200),
        pushed_at=now - timedelta(days=150),
        extracted_at=now,
    )
    assert (
        RepositoryMetricCalculator.calculate(r_180, reference_time=now).recency_bucket
        == RecencyBucket.LAST_180_DAYS
    )

    # OVER_180_DAYS
    r_over = make_record(
        created_at=now - timedelta(days=400),
        pushed_at=now - timedelta(days=300),
        extracted_at=now,
    )
    assert (
        RepositoryMetricCalculator.calculate(r_over, reference_time=now).recency_bucket
        == RecencyBucket.OVER_180_DAYS
    )


def test_issue_ratios_and_density() -> None:
    """issue_to_fork_ratio and issue_density_per_mb calculations."""
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)

    # 10 issues, 20 forks, 2048 KB (2.0 MB)
    rec = make_record(
        created_at=now - timedelta(days=50),
        pushed_at=now - timedelta(days=1),
        extracted_at=now,
        forks_count=20,
        open_issues_count=10,
        size_kb=2048,
    )
    m = RepositoryMetricCalculator.calculate(rec, reference_time=now)
    assert m.issue_to_fork_ratio == 0.5
    assert m.issue_density_per_mb == 5.0  # 10 issues / 2.0 MB
    assert m.repository_age_days == 50

    # Zero forks & zero size
    rec_zero = make_record(
        created_at=now,
        pushed_at=now,
        extracted_at=now,
        forks_count=0,
        open_issues_count=5,
        size_kb=0,
    )
    m_zero = RepositoryMetricCalculator.calculate(rec_zero, reference_time=now)
    assert m_zero.issue_to_fork_ratio == 0.0
    assert m_zero.issue_density_per_mb == 0.0
