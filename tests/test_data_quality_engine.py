"""Tests for the data quality validation engine and rules."""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from typing import Any

from analytics.quality.engine import DataQualityEngine
from analytics.quality.models import QualitySeverity
from analytics.quality.rules import (
    ExpectedVisibilityRule,
    ExtractedAtPresentRule,
    FullNamePatternRule,
    HtmlUrlValidityRule,
    NonEmptyFullNameRule,
    NonEmptyOwnerRule,
    NonNegativeMetricsRule,
    OwnerFullNameConsistencyRule,
    PushedAtConsistencyRule,
    TemporalConsistencyRule,
    UniqueFullNameRule,
    UniqueRepositoryIdRule,
    ValidRepositoryIdRule,
)


def sample_valid_record(**overrides: Any) -> dict[str, Any]:
    """Base clean repository record dictionary for data quality testing."""
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    base = {
        "repository_id": 500,
        "repository_name": "data-engine",
        "full_name": "acme/data-engine",
        "owner_login": "acme",
        "description": "Core engine",
        "visibility": "public",
        "default_branch": "main",
        "language": "Python",
        "is_fork": False,
        "is_archived": False,
        "is_disabled": False,
        "created_at": (now - timedelta(days=100)).isoformat(),
        "updated_at": (now - timedelta(days=10)).isoformat(),
        "pushed_at": (now - timedelta(days=5)).isoformat(),
        "stars_count": 150,
        "forks_count": 30,
        "open_issues_count": 4,
        "subscribers_count": 20,
        "size_kb": 12000,
        "html_url": "https://github.com/acme/data-engine",
        "extracted_at": now.isoformat(),
    }
    if (
        "full_name" in overrides
        and "repository_name" not in overrides
        and "/" in str(overrides["full_name"])
    ):
        parts = str(overrides["full_name"]).split("/")
        if len(parts) == 2:
            base["repository_name"] = parts[1]

    base.update(overrides)
    return base


def test_valid_record_passes_all_rules() -> None:
    """A clean record must trigger zero issues in DataQualityEngine."""
    engine = DataQualityEngine()
    record = sample_valid_record()
    result = engine.evaluate_record(record)

    assert result.is_valid is True
    assert result.has_errors is False
    assert result.has_warnings is False
    assert result.passed_records == 1
    assert result.failed_records == 0
    assert len(result.issues) == 0


def test_rule_valid_repository_id() -> None:
    """ValidRepositoryIdRule detects zero, negative, or invalid types."""
    rule = ValidRepositoryIdRule()

    assert len(rule.evaluate(sample_valid_record(repository_id=123))) == 0

    issues_zero = rule.evaluate(sample_valid_record(repository_id=0))
    assert len(issues_zero) == 1
    assert issues_zero[0].severity == QualitySeverity.ERROR
    assert "must be positive" in issues_zero[0].message

    issues_neg = rule.evaluate(sample_valid_record(repository_id=-5))
    assert len(issues_neg) == 1

    issues_str = rule.evaluate(sample_valid_record(repository_id="invalid"))
    assert len(issues_str) == 1


def test_rule_full_name_and_owner() -> None:
    """Tests for non-empty names and pattern validation."""
    rule_name = NonEmptyFullNameRule()
    assert len(rule_name.evaluate(sample_valid_record(full_name=""))) == 1
    assert len(rule_name.evaluate(sample_valid_record(full_name="   "))) == 1

    rule_pattern = FullNamePatternRule()
    assert len(rule_pattern.evaluate(sample_valid_record(full_name="acme-repo"))) == 1

    rule_owner = NonEmptyOwnerRule()
    assert len(rule_owner.evaluate(sample_valid_record(owner_login=""))) == 1


def test_rule_owner_full_name_consistency() -> None:
    """Owner login must match prefix of full_name."""
    rule = OwnerFullNameConsistencyRule()

    clean = sample_valid_record(owner_login="acme", full_name="acme/data-engine")
    assert len(rule.evaluate(clean)) == 0

    mismatch = sample_valid_record(
        owner_login="different", full_name="acme/data-engine"
    )
    issues = rule.evaluate(mismatch)
    assert len(issues) == 1
    assert issues[0].severity == QualitySeverity.ERROR
    assert "Identity mismatch" in issues[0].message


def test_rule_non_negative_metrics() -> None:
    """Numeric counters cannot be negative."""
    rule = NonNegativeMetricsRule()

    clean = sample_valid_record()
    assert len(rule.evaluate(clean)) == 0

    corrupted = sample_valid_record(stars_count=-10, forks_count=-1)
    issues = rule.evaluate(corrupted)
    assert len(issues) == 2
    for issue in issues:
        assert issue.severity == QualitySeverity.ERROR
        assert "cannot be negative" in issue.message


def test_rule_visibility() -> None:
    """Visibility outside public, private, internal must trigger error."""
    rule = ExpectedVisibilityRule()

    assert len(rule.evaluate(sample_valid_record(visibility="public"))) == 0
    assert len(rule.evaluate(sample_valid_record(visibility="private"))) == 0
    assert len(rule.evaluate(sample_valid_record(visibility="internal"))) == 0

    issues = rule.evaluate(sample_valid_record(visibility="secret"))
    assert len(issues) == 1
    assert issues[0].severity == QualitySeverity.ERROR


def test_rule_extracted_at() -> None:
    """Missing or invalid extracted_at must trigger error."""
    rule = ExtractedAtPresentRule()

    missing = sample_valid_record(extracted_at=None)
    assert len(rule.evaluate(missing)) == 1

    invalid = sample_valid_record(extracted_at="not-a-timestamp")
    assert len(rule.evaluate(invalid)) == 1


def test_rule_temporal_consistency() -> None:
    """Temporal inconsistencies between created, updated, and extracted timestamps."""
    rule = TemporalConsistencyRule()
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)

    # Anomaly 1: updated_at < created_at
    bad_order = sample_valid_record(
        created_at=(now - timedelta(days=10)).isoformat(),
        updated_at=(now - timedelta(days=20)).isoformat(),
        extracted_at=now.isoformat(),
    )
    issues = rule.evaluate(bad_order)
    assert any("updated_at" in i.field for i in issues)

    # Anomaly 2: created_at in the future relative to extracted_at
    future_create = sample_valid_record(
        created_at=(now + timedelta(days=5)).isoformat(),
        updated_at=(now + timedelta(days=5)).isoformat(),
        extracted_at=now.isoformat(),
    )
    issues_future = rule.evaluate(future_create)
    assert any("in the future" in i.message for i in issues_future)


def test_rule_pushed_at_consistency() -> None:
    """Pushed at earlier than creation triggers WARNING, not ERROR."""
    rule = PushedAtConsistencyRule()
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)

    anomaly = sample_valid_record(
        created_at=now.isoformat(),
        pushed_at=(now - timedelta(days=5)).isoformat(),
    )
    issues = rule.evaluate(anomaly)
    assert len(issues) == 1
    assert issues[0].severity == QualitySeverity.WARNING


def test_rule_html_url_validity() -> None:
    """Invalid URL triggers WARNING."""
    rule = HtmlUrlValidityRule()

    bad_url = sample_valid_record(html_url="ftp://invalid-url.com")
    issues = rule.evaluate(bad_url)
    assert len(issues) == 1
    assert issues[0].severity == QualitySeverity.WARNING


def test_batch_duplicate_rules() -> None:
    """Batch rules must detect duplicate repository_id and duplicate full_name."""
    rec1 = sample_valid_record(repository_id=101, full_name="acme/repo-1")
    rec2 = sample_valid_record(repository_id=101, full_name="acme/repo-2")  # Dup ID
    rec3 = sample_valid_record(repository_id=103, full_name="acme/repo-1")  # Dup Name

    batch_id_rule = UniqueRepositoryIdRule()
    id_issues = batch_id_rule.evaluate_batch([rec1, rec2, rec3])
    assert len(id_issues) == 1
    assert id_issues[0].severity == QualitySeverity.ERROR
    assert "Duplicate repository_id 101" in id_issues[0].message

    batch_name_rule = UniqueFullNameRule()
    name_issues = batch_name_rule.evaluate_batch([rec1, rec2, rec3])
    assert len(name_issues) == 1
    assert name_issues[0].severity == QualitySeverity.ERROR
    assert "Duplicate full_name 'acme/repo-1'" in name_issues[0].message


def test_non_destructive_guarantee() -> None:
    """Evaluating data quality must never mutate input records."""
    original = sample_valid_record(stars_count=-5, full_name="acme/test")
    clone = copy.deepcopy(original)

    engine = DataQualityEngine()
    engine.evaluate_record(original)
    engine.evaluate_batch([original, original])

    assert original == clone


def test_quality_result_methods() -> None:
    """QualityResult helper query methods work as expected."""
    engine = DataQualityEngine()
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)

    # 1 valid, 1 with ERROR, 1 with WARNING
    rec_valid = sample_valid_record(
        repository_id=1, full_name="org/r1", owner_login="org"
    )
    rec_error = sample_valid_record(
        repository_id=2, full_name="org/r2", owner_login="org", stars_count=-10
    )
    rec_warn = sample_valid_record(
        repository_id=3,
        full_name="org/r3",
        owner_login="org",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        pushed_at=(now - timedelta(days=2)).isoformat(),
    )

    result = engine.evaluate_batch([rec_valid, rec_error, rec_warn])

    assert result.is_valid is False
    assert result.has_errors is True
    assert result.has_warnings is True
    assert result.error_count == 1
    assert result.warning_count == 1

    error_issues = result.get_issues_by_severity(QualitySeverity.ERROR)
    assert len(error_issues) == 1
    assert error_issues[0].field == "stars_count"

    r2_issues = result.get_issues_for_record("org/r2")
    assert len(r2_issues) == 1

    serialized = result.to_dict()
    assert "summary" in serialized
    assert "issues" in serialized
    assert serialized["summary"]["error_count"] == 1


def test_rule_repository_name() -> None:
    """NonEmptyRepositoryNameRule validates non-emptiness and full_name alignment."""
    from analytics.quality.rules import NonEmptyRepositoryNameRule

    rule = NonEmptyRepositoryNameRule()

    # Clean
    assert len(rule.evaluate(sample_valid_record())) == 0

    # Empty name
    empty = sample_valid_record(repository_name="   ")
    issues_empty = rule.evaluate(empty)
    assert len(issues_empty) == 1
    assert issues_empty[0].severity == QualitySeverity.ERROR
    assert "missing or empty" in issues_empty[0].message

    # Name mismatch with full_name
    mismatch = sample_valid_record(
        repository_name="wrong-name", full_name="acme/data-engine"
    )
    issues_mismatch = rule.evaluate(mismatch)
    assert len(issues_mismatch) == 1
    assert "Identity mismatch" in issues_mismatch[0].message


def test_rule_default_branch() -> None:
    """NonEmptyDefaultBranchRule validates that default branch is non-empty."""
    from analytics.quality.rules import NonEmptyDefaultBranchRule

    rule = NonEmptyDefaultBranchRule()

    assert len(rule.evaluate(sample_valid_record(default_branch="main"))) == 0
    assert len(rule.evaluate(sample_valid_record(default_branch="master"))) == 0

    empty = sample_valid_record(default_branch="  ")
    issues = rule.evaluate(empty)
    assert len(issues) == 1
    assert issues[0].severity == QualitySeverity.ERROR
    assert issues[0].field == "default_branch"


def test_rule_nullability_check() -> None:
    """RequiredFieldsNullabilityRule detects missing non-nullable fields."""
    from analytics.quality.rules import RequiredFieldsNullabilityRule

    rule = RequiredFieldsNullabilityRule()

    clean = sample_valid_record()
    assert len(rule.evaluate(clean)) == 0

    # Test with multiple null fields
    corrupt = sample_valid_record()
    corrupt["repository_id"] = None
    corrupt["owner_login"] = None
    corrupt["stars_count"] = None

    issues = rule.evaluate(corrupt)
    assert len(issues) == 3
    fields_flagged = {i.field for i in issues}
    assert fields_flagged == {"repository_id", "owner_login", "stars_count"}
    for issue in issues:
        assert issue.severity == QualitySeverity.ERROR
