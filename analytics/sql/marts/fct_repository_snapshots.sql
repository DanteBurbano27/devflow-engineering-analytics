-- =============================================================================
-- Model: fct_repository_snapshots
-- Layer: Marts (Fact Table)
-- Dialect: Google Cloud BigQuery
-- Description: Historical periodic snapshot fact table capturing metrics,
--              community velocity, and health counters per repository extraction.
-- Partition By: snapshot_date (DATE(snapshot_timestamp))
-- Cluster By: repository_id, language
-- =============================================================================

WITH repository_activity AS (
    SELECT * FROM {{ ref('int_repository_activity') }}
)

SELECT
    DATE(extracted_at) AS snapshot_date,
    extracted_at AS snapshot_timestamp,
    repository_surrogate_key,
    repository_id,
    full_name,
    language,
    visibility,
    stars_count,
    forks_count,
    open_issues_count,
    subscribers_count,
    size_kb,
    community_interest_score,
    fork_to_star_ratio,
    issue_to_star_ratio,
    star_to_fork_ratio,
    issue_to_fork_ratio,
    issue_density_per_mb,
    days_since_last_push,
    recency_bucket,
    activity_status,
    is_active
FROM repository_activity;
