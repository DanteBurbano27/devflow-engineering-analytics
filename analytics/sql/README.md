# DevFlow Intelligence — BigQuery Warehouse Models

This directory contains BigQuery-ready SQL models for the repository analytics dimensional architecture. They are covered by static acceptance tests; real BigQuery execution is not claimed without cloud credentials and a deployed project.

## Modeling Architecture

```
[Raw GitHub Metadata Ingestion]
                │
                ▼
  [Staging: stg_github_repositories]
       (Types, Nulls, All Snapshots)
                │
                ▼
[Intermediate: int_repository_activity]
 (Temporal Delays, Ratios, Activity Status)
       │                        │
       ▼                        ▼
[Marts: dim_repositories]   [Marts: fct_repository_snapshots]
(Conformed Dimension)       (Partitioned Periodic Snapshot)
       │                        │
       └───────────┬────────────┘
                   ▼
     [Marts: agg_language_summary]
     [Marts: agg_owner_summary]
```

## Model Catalog

| Layer | Model | Materialization | Primary Key / Granularity | Description |
|---|---|---|---|---|
| Staging | `stg_github_repositories` | View / Incremental | `(repository_id, extracted_at)` | Cleans and casts every raw snapshot. |
| Intermediate | `int_repository_activity` | Ephemeral / View | `(repository_id, extracted_at)` | Calculates snapshot-level activity metrics. |
| Marts | `dim_repositories` | Table | `repository_surrogate_key` | Conformed repository dimension with latest attributes and statuses. |
| Marts | `fct_repository_snapshots` | Incremental Table | `(snapshot_date, repository_id)` | Fact table partitioned by `snapshot_date` capturing daily snapshot metrics. |
| Marts | `agg_language_summary` | View / Table | `language` | Fleet-level aggregated metrics segmented by programming language. |
| Marts | `agg_owner_summary` | View / Table | `owner_login` | Fleet-level aggregated metrics segmented by repository owner. |

## BigQuery Optimization Strategies

### 1. Partitioning
- `fct_repository_snapshots`: Partitioned by ingestion date:
  ```sql
  PARTITION BY DATE(snapshot_timestamp)
  ```
  Prevents full table scans when reporting on specific time windows.

### 2. Clustering
- `fct_repository_snapshots`: Clustered by `(repository_id, language)` to accelerate repository lookup and language slicing.
- `dim_repositories`: Clustered by `(language, visibility, owner_login)`.

### 3. Idempotency & Deduplication
- The repository dimension selects the latest snapshot with a window function:
  ```sql
  ROW_NUMBER() OVER (PARTITION BY repository_id ORDER BY extracted_at DESC, updated_at DESC)
  ```
- Generates 64-bit deterministic surrogate keys using `FARM_FINGERPRINT`.
