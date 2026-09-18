"""Unified facade service orchestrating the DevFlow analytics layer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from analytics.contracts.repository import (
    ContractValidationError,
    RepositoryContract,
    RepositoryRecord,
)
from analytics.metrics.calculator import RepositoryMetricCalculator
from analytics.metrics.definitions import RepositoryMetrics
from analytics.metrics.summary import (
    PortfolioAnalyticsAggregator,
    PortfolioSummary,
)
from analytics.quality.engine import DataQualityEngine
from analytics.quality.models import QualityResult, QualitySeverity
from ingestion.github.repository_metadata import RepositoryMetadata


class DataQualityValidationError(ValueError):
    """Raised when a contract-valid record fails an ERROR quality rule."""

    def __init__(self, quality_result: QualityResult) -> None:
        super().__init__(
            "Repository data quality validation failed with "
            f"{quality_result.error_count} error(s)."
        )
        self.quality_result = quality_result


class AnalyticsService:
    """High-level analytical orchestrator for DevFlow Intelligence.

    Validates contracts, verifies data quality, computes derived metrics,
    aggregates multi-repository portfolios, and produces exportable summaries.
    """

    def __init__(
        self,
        *,
        quality_engine: DataQualityEngine | None = None,
        metric_calculator: type[
            RepositoryMetricCalculator
        ] = RepositoryMetricCalculator,
        aggregator: type[PortfolioAnalyticsAggregator] = PortfolioAnalyticsAggregator,
    ) -> None:
        self.quality_engine = quality_engine or DataQualityEngine()
        self.metric_calculator = metric_calculator
        self.aggregator = aggregator

    def process_record(
        self,
        item: RepositoryMetadata | Mapping[str, Any] | RepositoryRecord,
        *,
        reference_time: datetime | None = None,
    ) -> tuple[RepositoryRecord, RepositoryMetrics, QualityResult]:
        """Validate, check quality, and derive metrics for a single repository.

        Raises ContractValidationError if the record does not satisfy contract.
        """
        # 1. Contract validation & normalization
        record = RepositoryContract.validate(item)

        # 2. Quality evaluation (non-destructive)
        quality_result = self.quality_engine.evaluate_record(record)
        if not quality_result.is_valid:
            raise DataQualityValidationError(quality_result)

        # 3. Derived metrics calculation
        metrics = self.metric_calculator.calculate(
            record,
            reference_time=reference_time,
        )

        return record, metrics, quality_result

    def process_batch(
        self,
        items: Sequence[RepositoryMetadata | Mapping[str, Any] | RepositoryRecord],
        *,
        reference_time: datetime | None = None,
        fail_on_contract_error: bool = False,
    ) -> tuple[list[RepositoryMetrics], QualityResult, PortfolioSummary]:
        """Process multiple repository records end-to-end.

        Evaluates dataset quality rules (e.g. uniqueness across batch),
        validates contracts, derives metrics for valid records, and produces
        a portfolio-level summary.
        """
        # 1. Execute batch quality checks
        quality_result = self.quality_engine.evaluate_batch(items)
        rejected_identifiers = {
            issue.record_identifier
            for issue in quality_result.issues
            if issue.severity == QualitySeverity.ERROR
            and issue.record_identifier is not None
        }

        # 2. Validate contracts and compute metrics
        valid_records: list[RepositoryRecord] = []
        metrics_list: list[RepositoryMetrics] = []

        for item in items:
            try:
                rec = RepositoryContract.validate(item)
                if (
                    rec.repository_id in rejected_identifiers
                    or rec.full_name in rejected_identifiers
                ):
                    continue
                valid_records.append(rec)
                m = self.metric_calculator.calculate(
                    rec,
                    reference_time=reference_time,
                )
                metrics_list.append(m)
            except ContractValidationError:
                if fail_on_contract_error:
                    raise

        # 3. Aggregate portfolio
        portfolio_summary = self.aggregator.aggregate(metrics_list)

        return metrics_list, quality_result, portfolio_summary

    def generate_report(
        self,
        items: Sequence[RepositoryMetadata | Mapping[str, Any] | RepositoryRecord],
        *,
        reference_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Generate a complete, serializable analytical report for an ingested batch."""
        metrics_list, quality_result, portfolio_summary = self.process_batch(
            items,
            reference_time=reference_time,
        )

        return {
            "meta": {
                "generated_at": datetime.now(UTC).isoformat(),
                "contract_version": RepositoryContract.SCHEMA_VERSION,
                "total_input_records": len(items),
                "processed_records": len(metrics_list),
            },
            "quality": quality_result.to_dict(),
            "portfolio": portfolio_summary.to_dict(),
            "repositories": [m.to_dict() for m in metrics_list],
        }
