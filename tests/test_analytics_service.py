"""End-to-end integration tests for AnalyticsService."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from analytics.contracts.repository import ContractValidationError
from analytics.service import AnalyticsService


def make_payload(
    repo_id: int,
    name: str,
    owner: str,
    stars: int,
    **kwargs: object,
) -> dict:
    """Generate valid repository metadata dictionary."""
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)
    base = {
        "repository_id": repo_id,
        "repository_name": name,
        "full_name": f"{owner}/{name}",
        "owner_login": owner,
        "description": "Integration test repo",
        "visibility": "public",
        "default_branch": "main",
        "language": "Python",
        "is_fork": False,
        "is_archived": False,
        "is_disabled": False,
        "created_at": (now - timedelta(days=60)).isoformat(),
        "updated_at": (now - timedelta(days=5)).isoformat(),
        "pushed_at": (now - timedelta(days=2)).isoformat(),
        "stars_count": stars,
        "forks_count": 10,
        "open_issues_count": 2,
        "subscribers_count": 8,
        "size_kb": 1200,
        "html_url": f"https://github.com/{owner}/{name}",
        "extracted_at": now.isoformat(),
    }
    base.update(kwargs)
    return base


def test_service_process_single_record() -> None:
    """process_record must return record, metrics, and quality result."""
    service = AnalyticsService()
    payload = make_payload(1, "repo-1", "org", stars=50)

    record, metrics, quality = service.process_record(payload)

    assert record.repository_id == 1
    assert metrics.stars_count == 50
    assert metrics.is_active is True
    assert quality.is_valid is True


def test_service_process_single_record_contract_failure() -> None:
    """process_record must raise ContractValidationError on invalid schema."""
    service = AnalyticsService()
    bad_payload = make_payload(1, "repo-1", "org", stars=-5)

    with pytest.raises(ContractValidationError):
        service.process_record(bad_payload)


def test_service_process_batch_clean() -> None:
    """process_batch with valid records derives metrics and aggregates portfolio."""
    service = AnalyticsService()
    batch = [
        make_payload(1, "repo-1", "org", stars=100),
        make_payload(2, "repo-2", "org", stars=200),
    ]

    metrics_list, quality_res, summary = service.process_batch(batch)

    assert len(metrics_list) == 2
    assert quality_res.is_valid is True
    assert summary.total_repositories == 2
    assert summary.total_stars == 300
    assert summary.avg_stars == 150.0


def test_service_process_batch_with_contract_errors_graceful() -> None:
    """By default, process_batch filters out invalid records while logging DQ issues."""
    service = AnalyticsService()
    batch = [
        make_payload(1, "valid-repo", "org", stars=100),
        make_payload(2, "invalid-repo", "org", stars=-50),  # Contract failure
    ]

    metrics_list, quality_res, summary = service.process_batch(
        batch,
        fail_on_contract_error=False,
    )

    assert len(metrics_list) == 1
    assert metrics_list[0].repository_name == "valid-repo"
    assert quality_res.is_valid is False
    assert quality_res.error_count >= 1
    assert summary.total_repositories == 1
    assert summary.total_stars == 100


def test_service_process_batch_fail_on_contract_error() -> None:
    """When fail_on_contract_error=True, invalid records trigger exception."""
    service = AnalyticsService()
    batch = [
        make_payload(1, "valid-repo", "org", stars=100),
        make_payload(2, "invalid-repo", "org", stars=-50),
    ]

    with pytest.raises(ContractValidationError):
        service.process_batch(batch, fail_on_contract_error=True)


def test_service_generate_report() -> None:
    """generate_report produces a structured, JSON-serializable dictionary."""
    service = AnalyticsService()
    batch = [
        make_payload(1, "repo-1", "org", stars=80),
        make_payload(2, "repo-2", "org", stars=120),
    ]

    report = service.generate_report(batch)

    assert "meta" in report
    assert "quality" in report
    assert "portfolio" in report
    assert "repositories" in report

    assert report["meta"]["total_input_records"] == 2
    assert report["meta"]["processed_records"] == 2
    assert report["portfolio"]["summary_metrics"]["total_stars"] == 200
    assert len(report["repositories"]) == 2
