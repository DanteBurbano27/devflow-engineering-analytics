# Release Checklist

## Pre-Release (Analytics)
- [ ] Run the complete collected test suite using Python 3.12 or newer: `python -m pytest`.
- [ ] Validate linting rules using `python -m ruff check .`.
- [ ] Confirm code formatting using `python -m ruff format --check .`.
- [ ] Run Integration Simulation (`tests/test_integration_simulation.py`) against Golden Data.
- [ ] When a BigQuery project is available, compile and execute SQL against a disposable dataset; V1 tests are static only.

## Release Execution
- [ ] Review the release diff and CI result on the release PR.
- [ ] Validate normalized outputs using the simulation constraints.

## Post-Release
- [ ] For a deployed scheduler, define and validate monitoring before enabling recurring runs.
