"""Data quality package for DevFlow Intelligence Analytics."""

from __future__ import annotations

from analytics.quality.engine import DataQualityEngine
from analytics.quality.models import (
    QualityIssue,
    QualityReport,
    QualityResult,
    QualitySeverity,
)
from analytics.quality.rules import (
    BatchQualityRule,
    ExpectedVisibilityRule,
    ExtractedAtPresentRule,
    FullNamePatternRule,
    HtmlUrlValidityRule,
    NonEmptyFullNameRule,
    NonEmptyOwnerRule,
    NonNegativeMetricsRule,
    OwnerFullNameConsistencyRule,
    PushedAtConsistencyRule,
    QualityRule,
    TemporalConsistencyRule,
    UniqueFullNameRule,
    UniqueRepositoryIdRule,
    ValidRepositoryIdRule,
)

__all__ = [
    "BatchQualityRule",
    "DataQualityEngine",
    "ExpectedVisibilityRule",
    "ExtractedAtPresentRule",
    "FullNamePatternRule",
    "HtmlUrlValidityRule",
    "NonEmptyFullNameRule",
    "NonEmptyOwnerRule",
    "NonNegativeMetricsRule",
    "OwnerFullNameConsistencyRule",
    "PushedAtConsistencyRule",
    "QualityIssue",
    "QualityReport",
    "QualityResult",
    "QualityRule",
    "QualitySeverity",
    "TemporalConsistencyRule",
    "UniqueFullNameRule",
    "UniqueRepositoryIdRule",
    "ValidRepositoryIdRule",
]
