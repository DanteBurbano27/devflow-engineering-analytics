"""Data quality validation engine executing configured rulesets."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from analytics.quality.models import QualityIssue, QualityResult
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
    _extract_dict,
    _get_identifier,
)


class DataQualityEngine:
    """Non-destructive data quality validation runner for repository metadata."""

    def __init__(
        self,
        *,
        record_rules: Sequence[QualityRule] | None = None,
        batch_rules: Sequence[BatchQualityRule] | None = None,
    ) -> None:
        if record_rules is None:
            self._record_rules: list[QualityRule] = [
                RequiredFieldsNullabilityRule(),
                ValidRepositoryIdRule(),
                NonEmptyRepositoryNameRule(),
                NonEmptyFullNameRule(),
                FullNamePatternRule(),
                NonEmptyOwnerRule(),
                OwnerFullNameConsistencyRule(),
                NonEmptyDefaultBranchRule(),
                NonNegativeMetricsRule(),
                ExpectedVisibilityRule(),
                ExtractedAtPresentRule(),
                TemporalConsistencyRule(),
                PushedAtConsistencyRule(),
                HtmlUrlValidityRule(),
            ]
        else:
            self._record_rules = list(record_rules)

        if batch_rules is None:
            self._batch_rules: list[BatchQualityRule] = [
                UniqueRepositoryIdRule(),
                UniqueFullNameRule(),
            ]
        else:
            self._batch_rules = list(batch_rules)

    @property
    def record_rules(self) -> tuple[QualityRule, ...]:
        """Configured record-level rules."""
        return tuple(self._record_rules)

    @property
    def batch_rules(self) -> tuple[BatchQualityRule, ...]:
        """Configured batch-level rules."""
        return tuple(self._batch_rules)

    def evaluate_record(self, record: Any) -> QualityResult:
        """Evaluate data quality rules for a single record."""
        issues: list[QualityIssue] = []
        rules_count = len(self._record_rules)

        for rule in self._record_rules:
            issues.extend(rule.evaluate(record))

        passed = 1 if not any(i.severity.value == "ERROR" for i in issues) else 0
        failed = 1 - passed

        return QualityResult(
            total_records=1,
            passed_records=passed,
            failed_records=failed,
            rules_evaluated=rules_count,
            issues=tuple(issues),
            evaluated_at=datetime.now(UTC),
        )

    def evaluate_batch(self, records: Sequence[Any]) -> QualityResult:
        """Evaluate data quality across a batch of records including batch rules."""
        issues: list[QualityIssue] = []
        records_list = list(records)
        total_records = len(records_list)

        if total_records == 0:
            return QualityResult(
                total_records=0,
                passed_records=0,
                failed_records=0,
                rules_evaluated=0,
                issues=(),
                evaluated_at=datetime.now(UTC),
            )

        rules_evaluated = (len(self._record_rules) * total_records) + len(
            self._batch_rules
        )

        failed_identifiers: set[str | int] = set()

        # 1. Record-level evaluations
        for r in records_list:
            rec_dict = _extract_dict(r)
            ident = _get_identifier(rec_dict) or id(r)
            rec_has_error = False

            for rule in self._record_rules:
                rule_issues = rule.evaluate(r)
                if rule_issues:
                    issues.extend(rule_issues)
                    if any(i.severity.value == "ERROR" for i in rule_issues):
                        rec_has_error = True

            if rec_has_error:
                failed_identifiers.add(ident)

        # 2. Batch-level evaluations
        for batch_rule in self._batch_rules:
            batch_issues = batch_rule.evaluate_batch(records_list)
            if batch_issues:
                issues.extend(batch_issues)
                for issue in batch_issues:
                    if (
                        issue.severity.value == "ERROR"
                        and issue.record_identifier is not None
                    ):
                        failed_identifiers.add(issue.record_identifier)

        failed_count = len(failed_identifiers)
        passed_count = max(0, total_records - failed_count)

        return QualityResult(
            total_records=total_records,
            passed_records=passed_count,
            failed_records=failed_count,
            rules_evaluated=rules_evaluated,
            issues=tuple(issues),
            evaluated_at=datetime.now(UTC),
        )
