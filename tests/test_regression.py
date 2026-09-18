import pytest

from analytics.contracts.repository import ContractValidationError, RepositoryContract
from analytics.metrics.calculator import RepositoryMetricCalculator
from analytics.quality.engine import DataQualityEngine
from tests.fixtures.golden_data import GOLDEN_REPOSITORIES


def test_golden_dataset_regression():
    engine = DataQualityEngine()
    calculator = RepositoryMetricCalculator()

    # Test valid repository
    valid_repo = GOLDEN_REPOSITORIES[0]
    record = RepositoryContract.validate(valid_repo)
    assert record.repository_name == "perfect-repo"

    evaluation = engine.evaluate_record(record)
    assert evaluation.is_valid

    metrics = calculator.calculate(record)
    assert metrics.repository_age_days >= 0
    assert metrics.issue_density_per_mb is not None

    # Test forked repo
    fork_repo = GOLDEN_REPOSITORIES[1]
    record2 = RepositoryContract.validate(fork_repo)
    evaluation2 = engine.evaluate_record(record2)
    assert evaluation2.is_valid
    metrics2 = calculator.calculate(record2)
    assert metrics2.recency_bucket is not None

    # Test archived repo
    archived_repo = GOLDEN_REPOSITORIES[2]
    record3 = RepositoryContract.validate(archived_repo)
    evaluation3 = engine.evaluate_record(record3)
    assert evaluation3.is_valid
    metrics3 = calculator.calculate(record3)
    assert metrics3.issue_to_fork_ratio is not None

    # Test invalid repo
    invalid_repo = GOLDEN_REPOSITORIES[3]
    with pytest.raises(ContractValidationError):
        RepositoryContract.validate(invalid_repo)
