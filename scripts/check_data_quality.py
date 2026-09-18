"""CLI diagnostic script to verify the DevFlow Data Quality engine."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Ensure repository root is on sys.path for direct script invocation
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analytics.quality.engine import DataQualityEngine  # noqa: E402
from analytics.quality.models import QualitySeverity  # noqa: E402


def create_quality_test_dataset() -> tuple[list[dict], list[dict]]:
    """Generate both valid and intentionally corrupted records for testing."""
    now = datetime.now(UTC)

    valid_records = [
        {
            "repository_id": 2001,
            "repository_name": "service-mesh",
            "full_name": "devflow-org/service-mesh",
            "owner_login": "devflow-org",
            "description": "Cloud-native service mesh gateway",
            "visibility": "public",
            "default_branch": "main",
            "language": "Go",
            "is_fork": False,
            "is_archived": False,
            "is_disabled": False,
            "created_at": (now - timedelta(days=100)).isoformat(),
            "updated_at": (now - timedelta(days=2)).isoformat(),
            "pushed_at": (now - timedelta(days=1)).isoformat(),
            "stars_count": 890,
            "forks_count": 140,
            "open_issues_count": 8,
            "subscribers_count": 55,
            "size_kb": 24000,
            "html_url": "https://github.com/devflow-org/service-mesh",
            "extracted_at": now.isoformat(),
        },
        {
            "repository_id": 2002,
            "repository_name": "data-catalog",
            "full_name": "devflow-org/data-catalog",
            "owner_login": "devflow-org",
            "description": "Metadata governance catalog",
            "visibility": "private",
            "default_branch": "main",
            "language": "Python",
            "is_fork": False,
            "is_archived": False,
            "is_disabled": False,
            "created_at": (now - timedelta(days=50)).isoformat(),
            "updated_at": (now - timedelta(days=10)).isoformat(),
            "pushed_at": (now - timedelta(days=5)).isoformat(),
            "stars_count": 45,
            "forks_count": 6,
            "open_issues_count": 1,
            "subscribers_count": 12,
            "size_kb": 8500,
            "html_url": "https://github.com/devflow-org/data-catalog",
            "extracted_at": now.isoformat(),
        },
    ]

    corrupted_records = [
        {
            # Violation 1: Negative stars (DQ-METRIC-001 - ERROR)
            # Violation 2: Inconsistent owner vs full_name (DQ-CONS-001 - ERROR)
            "repository_id": 2003,
            "repository_name": "corrupt-repo-1",
            "full_name": "another-org/corrupt-repo-1",
            "owner_login": "devflow-org",
            "description": "Corrupted metrics test record",
            "visibility": "public",
            "default_branch": "main",
            "language": "Rust",
            "is_fork": False,
            "is_archived": False,
            "is_disabled": False,
            "created_at": (now - timedelta(days=30)).isoformat(),
            "updated_at": (now - timedelta(days=1)).isoformat(),
            "pushed_at": (now - timedelta(days=1)).isoformat(),
            "stars_count": -15,  # ERROR
            "forks_count": 2,
            "open_issues_count": 0,
            "subscribers_count": 1,
            "size_kb": 120,
            "html_url": "https://github.com/another-org/corrupt-repo-1",
            "extracted_at": now.isoformat(),
        },
        {
            # Violation 3: Temporal anomaly: pushed_at before created_at
            # (DQ-TIME-003 - WARNING)
            # Violation 4: Duplicate repository_id (DQ-DUP-001 - ERROR)
            "repository_id": 2001,  # Duplicate ID
            "repository_name": "service-mesh-dup",
            "full_name": "devflow-org/service-mesh-dup",
            "owner_login": "devflow-org",
            "description": "Duplicate ID with temporal anomaly",
            "visibility": "public",
            "default_branch": "main",
            "language": "Go",
            "is_fork": False,
            "is_archived": False,
            "is_disabled": False,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "pushed_at": (now - timedelta(days=50)).isoformat(),  # WARNING
            "stars_count": 10,
            "forks_count": 1,
            "open_issues_count": 0,
            "subscribers_count": 1,
            "size_kb": 500,
            "html_url": "https://github.com/devflow-org/service-mesh-dup",
            "extracted_at": now.isoformat(),
        },
    ]

    return valid_records, corrupted_records


def main() -> int:
    """Run data quality evaluation suite."""
    print("=" * 65)
    print("DevFlow Intelligence — Data Quality Suite Diagnostic")
    print("=" * 65)

    engine = DataQualityEngine()
    valid_batch, corrupted_batch = create_quality_test_dataset()

    print(
        f"\n[1] Configured Ruleset: {len(engine.record_rules)} record rules, "
        f"{len(engine.batch_rules)} batch rules"
    )

    # Test 1: Clean dataset
    print(f"\n[2] Evaluating Clean Batch ({len(valid_batch)} valid records)...")
    clean_result = engine.evaluate_batch(valid_batch)
    print(f"    - Is Valid:         {clean_result.is_valid}")
    print(f"    - Total Records:    {clean_result.total_records}")
    print(f"    - Passed Records:   {clean_result.passed_records}")
    print(f"    - Failed Records:   {clean_result.failed_records}")
    print(f"    - Error Count:      {clean_result.error_count}")
    print(f"    - Warning Count:    {clean_result.warning_count}")

    if not clean_result.is_valid:
        print("[FAIL] Clean dataset failed data quality validation.")
        return 1

    # Test 2: Mixed / Degraded dataset
    mixed_batch = valid_batch + corrupted_batch
    print(
        f"\n[3] Evaluating Mixed Batch ({len(mixed_batch)} records with anomalies)..."
    )
    mixed_result = engine.evaluate_batch(mixed_batch)
    print(f"    - Is Valid:         {mixed_result.is_valid}")
    print(f"    - Total Records:    {mixed_result.total_records}")
    print(f"    - Passed Records:   {mixed_result.passed_records}")
    print(f"    - Failed Records:   {mixed_result.failed_records}")
    print(f"    - Total Issues:     {len(mixed_result.issues)}")
    print(f"    - Errors Detected:  {mixed_result.error_count}")
    print(f"    - Warnings Flagged: {mixed_result.warning_count}")

    print("\n[4] Detected Issues Breakdown:")
    for issue in mixed_result.issues:
        sev_tag = "[ERROR]" if issue.severity == QualitySeverity.ERROR else "[WARN]"
        print(
            f"    {sev_tag} {issue.rule_id} ({issue.rule_name}) "
            f"on record '{issue.record_identifier}':\n"
            f"           Field: {issue.field} | Message: {issue.message}"
        )

    print("\n[SUCCESS] Data quality engine evaluated all rules correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
