"""Portfolio-level multi-repository analytical aggregation."""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from analytics.metrics.definitions import ActivityStatus, RepositoryMetrics


@dataclass(frozen=True, slots=True)
class LanguageAnalytics:
    """Aggregated statistics for a specific programming language."""

    language: str
    repository_count: int
    percentage_of_total: float
    total_stars: int
    avg_stars: float
    total_forks: int
    active_count: int


@dataclass(frozen=True, slots=True)
class OwnerAnalytics:
    """Aggregated statistics for an organization or user owner."""

    owner_login: str
    repository_count: int
    total_stars: int
    total_forks: int
    total_open_issues: int
    languages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    """Executive portfolio summary aggregating multi-repository analytical health."""

    total_repositories: int
    total_stars: int
    total_forks: int
    total_open_issues: int
    total_subscribers: int
    total_size_kb: int

    avg_stars: float
    avg_forks: float
    avg_open_issues: float
    avg_size_kb: float
    median_stars: float
    median_forks: float

    active_count: int
    stale_count: int
    inactive_count: int
    archived_count: int
    disabled_count: int
    active_percentage: float

    languages: tuple[LanguageAnalytics, ...]
    owners: tuple[OwnerAnalytics, ...]
    top_starred_repositories: tuple[dict[str, Any], ...]

    generated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert portfolio summary to nested JSON-serializable dictionary."""
        return {
            "summary_metrics": {
                "total_repositories": self.total_repositories,
                "total_stars": self.total_stars,
                "total_forks": self.total_forks,
                "total_open_issues": self.total_open_issues,
                "total_subscribers": self.total_subscribers,
                "total_size_kb": self.total_size_kb,
                "avg_stars": self.avg_stars,
                "avg_forks": self.avg_forks,
                "avg_open_issues": self.avg_open_issues,
                "avg_size_kb": self.avg_size_kb,
                "median_stars": self.median_stars,
                "median_forks": self.median_forks,
            },
            "activity_health": {
                "active_count": self.active_count,
                "stale_count": self.stale_count,
                "inactive_count": self.inactive_count,
                "archived_count": self.archived_count,
                "disabled_count": self.disabled_count,
                "active_percentage": self.active_percentage,
            },
            "languages": [asdict(lang) for lang in self.languages],
            "owners": [asdict(owner) for owner in self.owners],
            "top_starred_repositories": list(self.top_starred_repositories),
            "generated_at": self.generated_at.isoformat(),
        }


class PortfolioAnalyticsAggregator:
    """Aggregates individual repository metrics into fleet-wide analytical views."""

    @classmethod
    def aggregate(cls, metrics_list: list[RepositoryMetrics]) -> PortfolioSummary:
        """Aggregate a collection of RepositoryMetrics into a PortfolioSummary."""
        total_repos = len(metrics_list)
        now = datetime.now(UTC)

        if total_repos == 0:
            return PortfolioSummary(
                total_repositories=0,
                total_stars=0,
                total_forks=0,
                total_open_issues=0,
                total_subscribers=0,
                total_size_kb=0,
                avg_stars=0.0,
                avg_forks=0.0,
                avg_open_issues=0.0,
                avg_size_kb=0.0,
                median_stars=0.0,
                median_forks=0.0,
                active_count=0,
                stale_count=0,
                inactive_count=0,
                archived_count=0,
                disabled_count=0,
                active_percentage=0.0,
                languages=(),
                owners=(),
                top_starred_repositories=(),
                generated_at=now,
            )

        total_stars = sum(m.stars_count for m in metrics_list)
        total_forks = sum(m.forks_count for m in metrics_list)
        total_open_issues = sum(m.open_issues_count for m in metrics_list)
        total_subscribers = sum(m.subscribers_count for m in metrics_list)
        total_size_kb = sum(m.size_kb for m in metrics_list)

        avg_stars = round(total_stars / total_repos, 2)
        avg_forks = round(total_forks / total_repos, 2)
        avg_open_issues = round(total_open_issues / total_repos, 2)
        avg_size_kb = round(total_size_kb / total_repos, 2)

        stars_series = [m.stars_count for m in metrics_list]
        forks_series = [m.forks_count for m in metrics_list]
        median_stars = float(statistics.median(stars_series))
        median_forks = float(statistics.median(forks_series))

        # Status counts
        active_count = sum(
            1 for m in metrics_list if m.activity_status == ActivityStatus.ACTIVE
        )
        stale_count = sum(
            1 for m in metrics_list if m.activity_status == ActivityStatus.STALE
        )
        inactive_count = sum(
            1 for m in metrics_list if m.activity_status == ActivityStatus.INACTIVE
        )
        archived_count = sum(
            1 for m in metrics_list if m.activity_status == ActivityStatus.ARCHIVED
        )
        disabled_count = sum(
            1 for m in metrics_list if m.activity_status == ActivityStatus.DISABLED
        )
        active_pct = round((active_count / total_repos) * 100, 2)

        # Language distribution
        lang_groups: dict[str, list[RepositoryMetrics]] = defaultdict(list)
        for m in metrics_list:
            lang_key = m.language if m.language is not None else "Unknown"
            lang_groups[lang_key].append(m)

        languages_analytics: list[LanguageAnalytics] = []
        for lang_name, group in sorted(
            lang_groups.items(), key=lambda x: len(x[1]), reverse=True
        ):
            l_count = len(group)
            l_stars = sum(item.stars_count for item in group)
            l_forks = sum(item.forks_count for item in group)
            l_active = sum(1 for item in group if item.is_active)
            languages_analytics.append(
                LanguageAnalytics(
                    language=lang_name,
                    repository_count=l_count,
                    percentage_of_total=round((l_count / total_repos) * 100, 2),
                    total_stars=l_stars,
                    avg_stars=round(l_stars / l_count, 2),
                    total_forks=l_forks,
                    active_count=l_active,
                )
            )

        # Owner distribution
        owner_groups: dict[str, list[RepositoryMetrics]] = defaultdict(list)
        for m in metrics_list:
            owner_groups[m.owner_login].append(m)

        owners_analytics: list[OwnerAnalytics] = []
        for owner_login, group in sorted(
            owner_groups.items(), key=lambda x: len(x[1]), reverse=True
        ):
            o_count = len(group)
            o_stars = sum(item.stars_count for item in group)
            o_forks = sum(item.forks_count for item in group)
            o_issues = sum(item.open_issues_count for item in group)
            langs = tuple(
                sorted({item.language for item in group if item.language is not None})
            )
            owners_analytics.append(
                OwnerAnalytics(
                    owner_login=owner_login,
                    repository_count=o_count,
                    total_stars=o_stars,
                    total_forks=o_forks,
                    total_open_issues=o_issues,
                    languages=langs,
                )
            )

        # Top 5 starred repositories
        sorted_by_stars = sorted(
            metrics_list, key=lambda x: x.stars_count, reverse=True
        )[:5]
        top_starred = tuple(
            {
                "repository_id": r.repository_id,
                "full_name": r.full_name,
                "stars_count": r.stars_count,
                "language": r.language,
                "activity_status": r.activity_status.value,
            }
            for r in sorted_by_stars
        )

        return PortfolioSummary(
            total_repositories=total_repos,
            total_stars=total_stars,
            total_forks=total_forks,
            total_open_issues=total_open_issues,
            total_subscribers=total_subscribers,
            total_size_kb=total_size_kb,
            avg_stars=avg_stars,
            avg_forks=avg_forks,
            avg_open_issues=avg_open_issues,
            avg_size_kb=avg_size_kb,
            median_stars=median_stars,
            median_forks=median_forks,
            active_count=active_count,
            stale_count=stale_count,
            inactive_count=inactive_count,
            archived_count=archived_count,
            disabled_count=disabled_count,
            active_percentage=active_pct,
            languages=tuple(languages_analytics),
            owners=tuple(owners_analytics),
            top_starred_repositories=top_starred,
            generated_at=now,
        )
