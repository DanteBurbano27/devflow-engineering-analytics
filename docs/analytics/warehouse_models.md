# DevFlow Intelligence — BigQuery Warehouse Models

## 1. Overview and Architecture

DevFlow Intelligence transforms raw metadata into structured analytical layers inside **Google BigQuery**. The models are located under `analytics/sql/` and follow modern analytics engineering conventions.

```
                    devflow_raw.raw_repositories
                                 │
                                 ▼
              devflow_staging.stg_github_repositories
              (Deduplication, Type Casting, Null Handling)
                                 │
                                 ▼
             devflow_analytics.int_repository_activity
             (Temporal Delays, Ratios, Activity Classification)
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
devflow_analytics.dim_repositories   devflow_analytics.fct_repository_snapshots
 (Conformed Repository Dimension)       (Partitioned Daily Snapshot Fact)
                 │                               │
                 └───────────────┬───────────────┘
                                 ▼
             devflow_analytics.agg_language_summary
             devflow_analytics.agg_owner_summary
```

---

## 2. Model Specifications

### 2.1 Staging: `stg_github_repositories`
* **File Path**: `analytics/sql/staging/stg_github_repositories.sql`
* **Target Layer**: `devflow_staging`
* **Primary Key**: `repository_id`
* **Surrogate Key**: `FARM_FINGERPRINT(CONCAT(CAST(repository_id AS STRING), '|', full_name))`
* **Deduplication Strategy**:
  ```sql
  ROW_NUMBER() OVER (
      PARTITION BY repository_id
      ORDER BY extracted_at DESC, updated_at DESC
  ) = 1
  ```

### 2.2 Intermediate: `int_repository_activity`
* **File Path**: `analytics/sql/intermediate/int_repository_activity.sql`
* **Target Layer**: `devflow_analytics` (Ephemeral / Logical View)
* **Calculations**:
  * `days_since_last_push`: `TIMESTAMP_DIFF(extracted_at, pushed_at, DAY)`
  * `days_since_creation` / `repository_age_days`: `TIMESTAMP_DIFF(extracted_at, created_at, DAY)`
  * `recency_bucket`: `LAST_7_DAYS`, `LAST_30_DAYS`, `LAST_90_DAYS`, `LAST_180_DAYS`, `OVER_180_DAYS`, `NEVER_PUSHED`
  * `activity_status`: `ACTIVE` ($\le 90$d), `STALE` ($91-180$d), `INACTIVE` ($>180$d), `ARCHIVED`, `DISABLED`
  * `fork_to_star_ratio`: `ROUND(SAFE_DIVIDE(forks_count, stars_count), 4)`
  * `issue_to_star_ratio`: `ROUND(SAFE_DIVIDE(open_issues_count, stars_count), 4)`
  * `star_to_fork_ratio`: `ROUND(SAFE_DIVIDE(stars_count, forks_count), 4)`
  * `issue_to_fork_ratio`: `ROUND(SAFE_DIVIDE(open_issues_count, forks_count), 4)`
  * `issue_density_per_mb`: `ROUND(SAFE_DIVIDE(open_issues_count, SAFE_DIVIDE(size_kb, 1024.0)), 4)`
  * `community_interest_score`: `ROUND((stars_count * 1.0) + (forks_count * 2.0) + (subscribers_count * 1.5), 2)`

### 2.3 Mart: `dim_repositories`
* **File Path**: `analytics/sql/marts/dim_repositories.sql`
* **Target Layer**: `devflow_analytics`
* **Table Type**: Conformed Dimension Table (SCD Type 1)
* **Clustering**: `language`, `visibility`, `owner_login`
* **Granularity**: One row per distinct repository
* **Key Attributes**: Surrogate key (`FARM_FINGERPRINT`), identity (`repository_id`, `full_name`, `owner_login`), `recency_bucket`, `repository_age_days`, `activity_status`, `is_active`

### 2.4 Mart: `fct_repository_snapshots`
* **File Path**: `analytics/sql/marts/fct_repository_snapshots.sql`
* **Target Layer**: `devflow_analytics`
* **Table Type**: Periodic Snapshot Fact Table
* **Partitioning**: `PARTITION BY DATE(snapshot_timestamp)`
* **Clustering**: `repository_id`, `language`
* **Granularity**: One row per repository per ingestion snapshot
* **Key Metrics**: Stars, forks, issues, subscribers, ratios, `recency_bucket`, and `community_interest_score`

### 2.5 Marts: Fleet Aggregations
* **`agg_language_summary`**: Language-level breakdown of repository counts, star counts, averages, and active percentages.
* **`agg_owner_summary`**: Organization-level rollup showing portfolio ownership volume, total engagement, and technology stack spread.

---

## 3. Warehouse Optimization Guidelines

1. **Partition Pruning**: Always filter analytical queries on `snapshot_date` when querying `fct_repository_snapshots` to minimize BigQuery slot usage and query costs.
2. **Clustering Efficiency**: Clustering on `(repository_id, language)` ensures that multi-repository filters avoid scanning irrelevant columnar blocks.
3. **Idempotent Loads**: Deduplication via `QUALIFY ROW_NUMBER() ...` guarantees idempotency during pipeline backfills or replay runs.
