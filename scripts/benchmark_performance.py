import time
import tracemalloc
from datetime import UTC, datetime

from analytics.contracts.repository import RepositoryContract
from analytics.metrics.calculator import RepositoryMetricCalculator
from analytics.quality.engine import DataQualityEngine


def generate_mock_repos(count: int) -> list[dict]:
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC).isoformat()
    past = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC).isoformat()
    return [
        {
            "repository_id": 1000 + i,
            "repository_name": f"repo-{i}",
            "full_name": f"owner/repo-{i}",
            "owner_login": "owner",
            "description": "desc",
            "visibility": "public",
            "default_branch": "main",
            "language": "Python",
            "is_fork": False,
            "is_archived": False,
            "is_disabled": False,
            "created_at": past,
            "updated_at": now,
            "pushed_at": now,
            "stars_count": 10,
            "forks_count": 5,
            "open_issues_count": 2,
            "subscribers_count": 1,
            "size_kb": 1024,
            "html_url": f"https://github.com/owner/repo-{i}",
            "extracted_at": now,
        }
        for i in range(count)
    ]


def run_benchmark():
    engine = DataQualityEngine()
    calculator = RepositoryMetricCalculator()

    sizes = [100, 1000, 10000]
    results = []

    for size in sizes:
        repos = generate_mock_repos(size)

        tracemalloc.start()
        start_time = time.perf_counter()

        for repo_dict in repos:
            record = RepositoryContract.validate(repo_dict)
            engine.evaluate_record(record)
            calculator.calculate(record)

        end_time = time.perf_counter()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        duration = end_time - start_time
        peak_mb = peak / 1024 / 1024

        results.append(f"| {size} | {duration:.4f} s | {peak_mb:.2f} MB |")

    print("| Record Count | Execution Time | Peak Memory |")
    print("|--------------|----------------|-------------|")
    for res in results:
        print(res)


if __name__ == "__main__":
    run_benchmark()
