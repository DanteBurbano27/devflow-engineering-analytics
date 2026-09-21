from analytics.contracts.repository import RepositoryContract
from analytics.metrics.calculator import RepositoryMetricCalculator
from analytics.quality.engine import DataQualityEngine
from tests.fixtures.golden_data import GOLDEN_REPOSITORIES


def test_simulate_ingestion_integration():
    """Simulates normalized ingestion output flowing through the analytics pipeline."""
    engine = DataQualityEngine()
    calculator = RepositoryMetricCalculator()

    successful_records = 0
    failed_records = 0

    for raw_data in GOLDEN_REPOSITORIES:
        try:
            # 1. Contract Validation
            record = RepositoryContract.validate(raw_data)

            # 2. Quality Evaluation
            quality_result = engine.evaluate_record(record)
            if not quality_result.is_valid:
                failed_records += 1
                continue

            # 3. Metrics Calculation
            metrics = calculator.calculate(record)

            # 4. Success (in real life, write to Data Warehouse)
            successful_records += 1
            assert metrics is not None

        except Exception:
            failed_records += 1

    assert successful_records > 0
    assert failed_records > 0
