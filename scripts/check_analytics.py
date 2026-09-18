"""CLI diagnostic script to verify the DevFlow analytics engine."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Ensure repository root is on sys.path for direct script invocation
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analytics.contracts.repository import RepositoryContract  # noqa: E402
from analytics.service import AnalyticsService  # noqa: E402


def create_sample_payloads() -> list[dict]:
    """Generate realistic synthetic records for validation."""
    now = datetime.now(UTC)
    return [
        {
            "repository_id": 1001,
            "repository_name": "data-pipeline",
            "full_name": "devflow-org/data-pipeline",
            "owner_login": "devflow-org",
            "description": "Production ETL pipeline engine",
            "visibility": "public",
            "default_branch": "main",
            "language": "Python",
            "is_fork": False,
            "is_archived": False,
            "is_disabled": False,
            "created_at": (now - timedelta(days=200)).isoformat(),
            "updated_at": (now - timedelta(days=5)).isoformat(),
            "pushed_at": (now - timedelta(days=3)).isoformat(),
            "stars_count": 450,
            "forks_count": 85,
            "open_issues_count": 12,
            "subscribers_count": 30,
            "size_kb": 15400,
            "html_url": "https://github.com/devflow-org/data-pipeline",
            "extracted_at": now.isoformat(),
        },
        {
            "repository_id": 1002,
            "repository_name": "web-dashboard",
            "full_name": "devflow-org/web-dashboard",
            "owner_login": "devflow-org",
            "description": "Next.js analytical frontend",
            "visibility": "public",
            "default_branch": "main",
            "language": "TypeScript",
            "is_fork": False,
            "is_archived": False,
            "is_disabled": False,
            "created_at": (now - timedelta(days=365)).isoformat(),
            "updated_at": (now - timedelta(days=120)).isoformat(),
            "pushed_at": (now - timedelta(days=110)).isoformat(),
            "stars_count": 120,
            "forks_count": 22,
            "open_issues_count": 4,
            "subscribers_count": 15,
            "size_kb": 42000,
            "html_url": "https://github.com/devflow-org/web-dashboard",
            "extracted_at": now.isoformat(),
        },
        {
            "repository_id": 1003,
            "repository_name": "legacy-migration",
            "full_name": "devflow-org/legacy-migration",
            "owner_login": "devflow-org",
            "description": "Archived migration scripts",
            "visibility": "private",
            "default_branch": "master",
            "language": "Python",
            "is_fork": False,
            "is_archived": True,
            "is_disabled": False,
            "created_at": (now - timedelta(days=800)).isoformat(),
            "updated_at": (now - timedelta(days=400)).isoformat(),
            "pushed_at": (now - timedelta(days=400)).isoformat(),
            "stars_count": 15,
            "forks_count": 3,
            "open_issues_count": 0,
            "subscribers_count": 5,
            "size_kb": 2300,
            "html_url": "https://github.com/devflow-org/legacy-migration",
            "extracted_at": now.isoformat(),
        },
    ]


def main() -> int:
    """Run analytics pipeline demonstration."""
    print("=" * 65)
    print("DevFlow Intelligence — Analytics Engine Diagnostic")
    print(f"Contract Version: {RepositoryContract.SCHEMA_VERSION}")
    print("=" * 65)

    service = AnalyticsService()
    payloads = create_sample_payloads()

    print(f"\n[1] Processing batch of {len(payloads)} synthetic repositories...")
    report = service.generate_report(payloads)

    summary = report["portfolio"]["summary_metrics"]
    health = report["portfolio"]["activity_health"]

    print("\n[2] Fleet Summary Metrics:")
    print(f"    - Total Repositories: {summary['total_repositories']}")
    print(f"    - Total Stars:        {summary['total_stars']}")
    print(f"    - Total Forks:        {summary['total_forks']}")
    print(f"    - Average Stars:      {summary['avg_stars']}")
    print(f"    - Median Stars:       {summary['median_stars']}")

    print("\n[3] Activity & Health:")
    print(f"    - Active Repos:       {health['active_count']}")
    print(f"    - Stale Repos:        {health['stale_count']}")
    print(f"    - Archived Repos:     {health['archived_count']}")
    print(f"    - Active Ratio:       {health['active_percentage']}%")

    print("\n[4] Language Breakdown:")
    for lang in report["portfolio"]["languages"]:
        print(
            f"    - {lang['language']:<12}: {lang['repository_count']} repos "
            f"({lang['percentage_of_total']}%), {lang['total_stars']} stars"
        )

    print("\n[5] Detailed Derived Metrics per Repository:")
    for repo in report["repositories"]:
        print(
            f"    * {repo['full_name']:<30} | Status: {repo['activity_status']:<8} "
            f"| Push: {repo['days_since_last_push']}d ago "
            f"| Score: {repo['community_interest_score']}"
        )

    print("\n[6] JSON Report Serialization:")
    serialized = json.dumps(report, indent=2)
    print(f"    - Serialized payload size: {len(serialized)} bytes")
    print("\n[SUCCESS] Analytics diagnostic passed cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
