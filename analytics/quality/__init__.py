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
    NonEmptyDefaultBranchRule,
    NonEmptyFullNameRule,
    NonEmptyOwnerRule,
    NonEmptyRepositoryNameRule,
    NonNegativeMetricsRule,
    OwnerFullNameConsistencyRule,
    PushedAtConsistencyRule,
    QualityRule,
    RequiredFieldsNullabilityRule,
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
    "NonEmptyDefaultBranchRule",
    "NonEmptyFullNameRule",
    "NonEmptyOwnerRule",
    "NonEmptyRepositoryNameRule",
    "NonNegativeMetricsRule",
    "OwnerFullNameConsistencyRule",
    "PushedAtConsistencyRule",
    "QualityIssue",
    "QualityReport",
    "QualityResult",
    "QualityRule",
    "QualitySeverity",
    "RequiredFieldsNullabilityRule",
    "TemporalConsistencyRule",
    "UniqueFullNameRule",
    "UniqueRepositoryIdRule",
    "ValidRepositoryIdRule",
]
