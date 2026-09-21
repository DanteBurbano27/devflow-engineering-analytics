# Data Lineage

## Overview
This document traces the path of GitHub repository metadata from the ingestion layer to the analytical models in the analytics plane.

## Pipeline Stages

1. **Ingestion Layer**
   - **Source**: GitHub REST API
   - **Entity**: Raw JSON payload containing repository information.
   - **Transformation**: Flattened into a standardized dictionary.

2. **Contract Validation & Quality (Analytics Plane)**
   - **Component**: `RepositoryContract`
   - **Action**: Enforces data types, timezones, and non-null constraints.
   - **Component**: `DataQualityEngine`
   - **Action**: Identifies anomalous metrics (e.g., negative sizes, missing default branches).

3. **Metrics Calculation (Analytics Plane)**
   - **Component**: `RepositoryMetricCalculator`
   - **Action**: Augments the raw record with analytical fields:
     - `recency_bucket`
     - `repository_age_days`
     - `issue_density_per_mb`
     - `issue_to_fork_ratio`

4. **Data Warehouse (Analytics SQL)**
   - **Staging (`stg_github_repositories.sql`)**: Base view built from the raw extracted payloads.
   - **Intermediate (`int_repository_activity.sql`)**: Incorporates the metrics calculations directly in BigQuery.
   - **Marts (`dim_repositories.sql`, `fct_repository_snapshots.sql`, etc.)**: Fact and dimension tables utilized by BI tools.
