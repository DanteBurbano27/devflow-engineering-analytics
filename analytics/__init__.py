"""DevFlow Intelligence Analytics Layer.

Provides data contracts, quality assurance, derived metrics,
and analytical summaries for software engineering repository metadata.
"""

from __future__ import annotations

from analytics.contracts.repository import RepositoryContract, RepositoryRecord
from analytics.metrics.calculator import RepositoryMetricCalculator
from analytics.metrics.definitions import (
    ActivityStatus,
    RecencyBucket,
    RepositoryMetrics,
    SizeCategory,
)
from analytics.metrics.summary import (
    GovernanceDistribution,
    PortfolioAnalyticsAggregator,
    PortfolioSummary,
)
from analytics.quality.engine import DataQualityEngine
from analytics.quality.models import (
    QualityIssue,
    QualityReport,
    QualityResult,
    QualitySeverity,
)
from analytics.service import AnalyticsService, DataQualityValidationError

__all__ = [
    "ActivityStatus",
    "AnalyticsService",
    "DataQualityValidationError",
    "DataQualityEngine",
    "GovernanceDistribution",
    "PortfolioAnalyticsAggregator",
    "PortfolioSummary",
    "QualityIssue",
    "QualityReport",
    "QualityResult",
    "QualitySeverity",
    "RecencyBucket",
    "RepositoryContract",
    "RepositoryMetricCalculator",
    "RepositoryMetrics",
    "RepositoryRecord",
    "SizeCategory",
]
