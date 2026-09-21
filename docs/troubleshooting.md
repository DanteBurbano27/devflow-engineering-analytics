# Troubleshooting Guide

## Common Issues & Resolutions

### 1. ContractValidationError Spikes
**Symptom**: Pipeline halts or drops many records with `ContractValidationError`.
**Root Cause**: The upstream data source (ingestion layer) has modified the dictionary structure or dropped a required field (e.g., `visibility` or `default_branch`).
**Action**:
- Inspect the offending payload.
- Review upstream schema changes to verify if the change was intentional.
- If intentional, implement a MINOR or MAJOR version bump to `RepositoryContract`.

### 2. Unexpected Zero Ratios in Metrics
**Symptom**: Warehouse models show an unexpected increase in `0.0` ratios.
**Root Cause**: Python and SQL both use `0.0` when a ratio denominator is zero. A sudden increase can indicate many repositories lost star, fork, or size metadata.
**Action**: Review upstream GitHub API limits or pagination bugs in the ingestion layer.
