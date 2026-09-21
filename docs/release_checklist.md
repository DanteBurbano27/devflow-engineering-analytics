# Release Checklist

## Pre-Release (Analytics Plane)
- [ ] Ensure 100% test coverage using `py -3.14 -m pytest`.
- [ ] Validate linting rules using `py -3.14 -m ruff check .`.
- [ ] Confirm code formatting using `py -3.14 -m ruff format --check .`.
- [ ] Run Integration Simulation (`tests/test_integration_simulation.py`) against Golden Data.
- [ ] Verify BigQuery SQL scripts compile cleanly.

## Release Execution
- [ ] Merge analytics and data quality branch to integration branch.
- [ ] Validate downstream ingestion outputs using the simulation constraints.

## Post-Release
- [ ] Monitor metric deviation and quality error rates for the first 24 hours.
