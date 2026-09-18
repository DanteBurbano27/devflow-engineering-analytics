# Operational Runbook

## Overview
This runbook covers the standard operating procedures for the Antigravity Analytics plane in DevFlow Intelligence.

## Daily Operations
- Monitor execution logs for `ContractValidationError`. A spike in these errors indicates an upstream change in the GitHub API or Codex ingestion logic.
- Verify that `DataQualityEngine` reject rates remain stable (historically < 1%).
- Check BigQuery Dataform/dbt runs for the models in `analytics/sql/`.

## Service Level Objectives (SLOs)
- **TARGET (Phase 3)**: 99.9% of valid records processed within 5 seconds.
- **CURRENTLY IMPLEMENTED (Phase 2C)**: Local deterministic batch validation runs at ~3,000 records/sec.
