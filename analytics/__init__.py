"""DevFlow Intelligence Analytics Layer.

Provides data contracts, quality assurance, derived metrics,
and analytical summaries for software engineering repository metadata.
"""

from __future__ import annotations

from analytics.contracts.repository import RepositoryContract, RepositoryRecord
from analytics.metrics.calculator import RepositoryMetricCalculator
from analytics.metrics.definitions import ActivityStatus, RepositoryMetrics
from analytics.metrics.summary import PortfolioAnalyticsAggregator, PortfolioSummary
from analytics.quality.engine import DataQualityEngine
from analytics.quality.models import (
    QualityIssue,
    QualityReport,
    QualityResult,
    QualitySeverity,
)
from analytics.service import AnalyticsService

__all__ = [
    "ActivityStatus",
    "AnalyticsService",
    "DataQualityEngine",
    "PortfolioAnalyticsAggregator",
    "PortfolioSummary",
    "QualityIssue",
    "QualityReport",
    "QualityResult",
    "QualitySeverity",
    "RepositoryContract",
    "RepositoryMetricCalculator",
    "RepositoryMetrics",
    "RepositoryRecord",
]
