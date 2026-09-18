-- =============================================================================
-- Model: agg_language_summary
-- Layer: Marts (Aggregated Fleet Analytics)
-- Dialect: Google Cloud BigQuery
-- Description: Aggregates repository counts, community adoption, and maintenance
--              activity sliced by programming language across the fleet.
-- =============================================================================

WITH dim_repos AS (
    SELECT * FROM {{ ref('dim_repositories') }}
),

fct_snaps AS (
    SELECT * FROM {{ ref('fct_repository_snapshots') }}
    -- Filter to most recent snapshot per repository
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY repository_id
        ORDER BY snapshot_timestamp DESC
    ) = 1
)

SELECT
    COALESCE(r.language, 'Unknown') AS language,
    COUNT(DISTINCT r.repository_id) AS total_repositories,
    SUM(s.stars_count) AS total_stars,
    ROUND(AVG(s.stars_count), 2) AS avg_stars,
    SUM(s.forks_count) AS total_forks,
    ROUND(AVG(s.forks_count), 2) AS avg_forks,
    SUM(s.open_issues_count) AS total_open_issues,
    ROUND(AVG(s.open_issues_count), 2) AS avg_open_issues,
    SUM(s.size_kb) AS total_size_kb,
    COUNTIF(r.is_active) AS active_repositories_count,
    ROUND(SAFE_DIVIDE(COUNTIF(r.is_active) * 100.0, COUNT(DISTINCT r.repository_id)), 2) AS active_percentage,
    COUNTIF(r.is_archived) AS archived_repositories_count
FROM dim_repos r
JOIN fct_snaps s
    ON r.repository_id = s.repository_id
GROUP BY 1
ORDER BY total_repositories DESC, total_stars DESC;
