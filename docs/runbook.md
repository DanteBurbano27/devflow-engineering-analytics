# Operational Runbook

## Overview
This runbook separates current V1 local operations from target-state warehouse operations.

## Daily Operations
- Monitor execution logs for `ContractValidationError`. A spike in these errors indicates an upstream change in the GitHub API or ingestion normalization logic.
- Review `DataQualityEngine` errors and warnings against the 16-rule catalog; no historical reject-rate baseline is claimed.
- **Target state only:** after a BigQuery deployment exists, monitor the jobs that execute models in `analytics/sql/`. V1 has no deployed Dataform/dbt run.

## Service Level Objectives (SLOs)
- **TARGET (Phase 3)**: 99.9% of valid records processed within 5 seconds.
- **CURRENTLY OBSERVED (V1 local benchmark)**: Contract, quality, and metric processing completed 10,000 synthetic records in 3.9482 seconds (~2,533 records/sec) on Python 3.14.6. This is not a production SLO.
