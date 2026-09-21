# Integration Simulation

## Overview
This document outlines the simulated integration process between the ingestion data plane and the analytics plane. The simulation ensures that once the raw data is normalized by the ingestion layer, it flows seamlessly through our data quality, contract validation, and metric calculation layers.

## Simulation Pipeline
1. **Contract Validation**: Incoming dictionaries or `RepositoryMetadata` objects are validated against the `RepositoryContract`. Any schema violation or type mismatch will halt the process immediately.
2. **Quality Evaluation**: Validated records are passed to `DataQualityEngine.evaluate_record()` where deterministic rules evaluate nullability, extreme values, and logical constraints. Records failing ERROR level rules are rejected.
3. **Metric Calculation**: The surviving valid records proceed to `RepositoryMetricCalculator.calculate()` to compute `recency_bucket`, `issue_density_per_mb`, `issue_to_fork_ratio`, and other complex analytics metrics.
4. **Data Warehouse Delivery**: Finally, these rich records are ready for the BigQuery models.

## Expected Outcomes
The testing suite `tests/test_integration_simulation.py` confirms that:
- Valid repositories traverse the pipeline successfully.
- Edge cases like archived repositories are properly handled without calculation errors.
- Invalid repositories are explicitly rejected via `ContractValidationError` or failing quality checks.
