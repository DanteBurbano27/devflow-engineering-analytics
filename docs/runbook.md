# Operational Runbook

## Overview
This runbook covers the standard operating procedures for the Antigravity Analytics plane in DevFlow Intelligence.

## Daily Operations
- Monitor execution logs for `ContractValidationError`. A spike in these errors indicates an upstream change in the GitHub API or Codex ingestion logic.
- Verify that `DataQualityEngine` reject rates remain stable (historically < 1%).
- Check BigQuery Dataform/dbt runs for the models in `analytics/sql/`.

## Service Level Objectives (SLOs)
- **TARGET (Phase 3)**: 99.9% of valid records processed within 5 seconds.
- **CURRENTLY OBSERVED (V1 local benchmark)**: Contract, quality, and metric processing completed 10,000 synthetic records in 3.9482 seconds (~2,533 records/sec) on Python 3.14.6. This is not a production SLO.
