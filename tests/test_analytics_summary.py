"""Tests for multi-repository portfolio analytics aggregation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from analytics.contracts.repository import RepositoryRecord
from analytics.metrics.calculator import RepositoryMetricCalculator
from analytics.metrics.summary import PortfolioAnalyticsAggregator


def make_sample_record(
    repo_id: int,
    name: str,
    owner: str,
    lang: str | None,
    stars: int,
    forks: int,
    days_ago_push: int,
    is_archived: bool = False,
) -> RepositoryRecord:
    """Helper to produce a RepositoryRecord."""
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    return RepositoryRecord(
        repository_id=repo_id,
        repository_name=name,
        full_name=f"{owner}/{name}",
        owner_login=owner,
        description="Sample",
        visibility="public",
        default_branch="main",
        language=lang,
        is_fork=False,
        is_archived=is_archived,
        is_disabled=False,
        created_at=now - timedelta(days=300),
        updated_at=now - timedelta(days=days_ago_push),
        pushed_at=now - timedelta(days=days_ago_push),
        stars_count=stars,
        forks_count=forks,
        open_issues_count=5,
        subscribers_count=10,
        size_kb=1000,
        html_url=f"https://github.com/{owner}/{name}",
        extracted_at=now,
    )


def test_aggregate_empty_list() -> None:
    """Empty metrics list must produce valid zero-valued summary."""
    summary = PortfolioAnalyticsAggregator.aggregate([])

    assert summary.total_repositories == 0
    assert summary.total_stars == 0
    assert summary.avg_stars == 0.0
    assert summary.active_count == 0
    assert summary.active_percentage == 0.0
    assert len(summary.languages) == 0
    assert len(summary.owners) == 0


def test_aggregate_multi_repo_fleet() -> None:
    """Aggregating a fleet must compute accurate totals, averages, and groupings."""
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    records = [
        # Active Python repo
        make_sample_record(
            1,
            "repo-py-1",
            "team-alpha",
            "Python",
            stars=100,
            forks=20,
            days_ago_push=10,
        ),
        # Stale Python repo
        make_sample_record(
            2,
            "repo-py-2",
            "team-alpha",
            "Python",
            stars=200,
            forks=40,
            days_ago_push=120,
        ),
        # Inactive Go repo
        make_sample_record(
            3, "repo-go-1", "team-beta", "Go", stars=300, forks=60, days_ago_push=250
        ),
        # Archived Rust repo
        make_sample_record(
            4,
            "repo-rs-1",
            "team-alpha",
            "Rust",
            stars=400,
            forks=80,
            days_ago_push=15,
            is_archived=True,
        ),
    ]

    metrics_list = [
        RepositoryMetricCalculator.calculate(r, reference_time=now) for r in records
    ]
    summary = PortfolioAnalyticsAggregator.aggregate(metrics_list)

    # 1. Totals
    assert summary.total_repositories == 4
    assert summary.total_stars == 1000  # 100 + 200 + 300 + 400
    assert summary.total_forks == 200  # 20 + 40 + 60 + 80
    assert summary.avg_stars == 250.0
    assert summary.avg_forks == 50.0
    assert summary.median_stars == 250.0  # median of [100, 200, 300, 400] = 250.0

    # 2. Activity breakdown
    assert summary.active_count == 1
    assert summary.stale_count == 1
    assert summary.inactive_count == 1
    assert summary.archived_count == 1
    assert summary.disabled_count == 0
    assert summary.active_percentage == 25.0

    # 3. Languages
    lang_map = {lang.language: lang for lang in summary.languages}
    assert "Python" in lang_map
    assert lang_map["Python"].repository_count == 2
    assert lang_map["Python"].percentage_of_total == 50.0
    assert lang_map["Python"].total_stars == 300
    assert lang_map["Python"].avg_stars == 150.0
    assert lang_map["Python"].active_count == 1

    assert "Go" in lang_map
    assert lang_map["Go"].repository_count == 1
    assert lang_map["Go"].total_stars == 300

    # 4. Owners
    owner_map = {o.owner_login: o for o in summary.owners}
    assert "team-alpha" in owner_map
    assert owner_map["team-alpha"].repository_count == 3
    assert owner_map["team-alpha"].total_stars == 700
    assert set(owner_map["team-alpha"].languages) == {"Python", "Rust"}

    assert "team-beta" in owner_map
    assert owner_map["team-beta"].repository_count == 1
    assert owner_map["team-beta"].total_stars == 300

    # 5. Top Starred Repositories
    assert len(summary.top_starred_repositories) == 4
    assert summary.top_starred_repositories[0]["full_name"] == "team-alpha/repo-rs-1"
    assert summary.top_starred_repositories[0]["stars_count"] == 400
    assert summary.top_starred_repositories[3]["full_name"] == "team-alpha/repo-py-1"
    assert summary.top_starred_repositories[3]["stars_count"] == 100


def test_portfolio_summary_serialization() -> None:
    """PortfolioSummary.to_dict() must return a clean nested dictionary."""
    summary = PortfolioAnalyticsAggregator.aggregate([])
    data = summary.to_dict()

    assert "summary_metrics" in data
    assert "activity_health" in data
    assert "languages" in data
    assert "owners" in data
    assert "top_starred_repositories" in data
    assert data["summary_metrics"]["total_repositories"] == 0
