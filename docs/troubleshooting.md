# Troubleshooting Guide

## Common Issues & Resolutions

### 1. ContractValidationError Spikes
**Symptom**: Pipeline halts or drops many records with `ContractValidationError`.
**Root Cause**: The upstream data source (Codex ingestion) has modified the dictionary structure or dropped a required field (e.g., `visibility` or `default_branch`).
**Action**: 
- Inspect the offending payload.
- Coordinate with the Codex team to verify if the change was intentional.
- If intentional, implement a MINOR or MAJOR version bump to `RepositoryContract`.

### 2. Unexpected NULLs in Metrics
**Symptom**: Warehouse models show NULL for `issue_to_fork_ratio`.
**Root Cause**: While mathematically handled (divide by zero protection), a sudden increase implies many repositories lost their fork count metadata.
**Action**: Review upstream GitHub API limits or pagination bugs in the Codex ingestion layer.
