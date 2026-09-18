"""Data quality model definitions, severities, issues, and evaluation reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class QualitySeverity(StrEnum):
    """Classification of data quality rule breach severities."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True, slots=True)
class QualityIssue:
    """Individual data quality rule violation or observation."""

    rule_id: str
    rule_name: str
    severity: QualitySeverity
    field: str
    message: str
    record_identifier: str | int | None
    actual_value: Any

    def to_dict(self) -> dict[str, Any]:
        """Convert issue to serializable dictionary."""
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "field": self.field,
            "message": self.message,
            "record_identifier": self.record_identifier,
            "actual_value": str(self.actual_value)
            if self.actual_value is not None
            else None,
        }


@dataclass(frozen=True, slots=True)
class QualityResult:
    """Consolidated report of data quality execution over records."""

    total_records: int
    passed_records: int
    failed_records: int
    rules_evaluated: int
    issues: tuple[QualityIssue, ...]
    evaluated_at: datetime

    @property
    def is_valid(self) -> bool:
        """True if there are zero ERROR severity issues."""
        return self.error_count == 0

    @property
    def has_errors(self) -> bool:
        """True if at least one ERROR exists."""
        return self.error_count > 0

    @property
    def has_warnings(self) -> bool:
        """True if at least one WARNING exists."""
        return self.warning_count > 0

    @property
    def error_count(self) -> int:
        """Count of issues with ERROR severity."""
        return sum(1 for i in self.issues if i.severity == QualitySeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of issues with WARNING severity."""
        return sum(1 for i in self.issues if i.severity == QualitySeverity.WARNING)

    @property
    def info_count(self) -> int:
        """Count of issues with INFO severity."""
        return sum(1 for i in self.issues if i.severity == QualitySeverity.INFO)

    def get_issues_by_severity(self, severity: QualitySeverity) -> list[QualityIssue]:
        """Filter issues by specific severity."""
        return [i for i in self.issues if i.severity == severity]

    def get_issues_for_record(self, record_identifier: str | int) -> list[QualityIssue]:
        """Filter issues by record key."""
        return [i for i in self.issues if i.record_identifier == record_identifier]

    def to_dict(self) -> dict[str, Any]:
        """Serialize data quality evaluation results to dictionary."""
        return {
            "summary": {
                "is_valid": self.is_valid,
                "has_errors": self.has_errors,
                "has_warnings": self.has_warnings,
                "total_records": self.total_records,
                "passed_records": self.passed_records,
                "failed_records": self.failed_records,
                "rules_evaluated": self.rules_evaluated,
                "error_count": self.error_count,
                "warning_count": self.warning_count,
                "info_count": self.info_count,
                "evaluated_at": self.evaluated_at.isoformat(),
            },
            "issues": [i.to_dict() for i in self.issues],
        }


# Alias for backward compatibility / intuitive naming
QualityReport = QualityResult
