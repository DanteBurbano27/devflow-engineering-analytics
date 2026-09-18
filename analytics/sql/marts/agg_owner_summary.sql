-- =============================================================================
-- Model: agg_owner_summary
-- Layer: Marts (Aggregated Fleet Analytics)
-- Dialect: Google Cloud BigQuery
-- Description: Aggregates organization and user account metrics across repositories.
-- =============================================================================

WITH dim_repos AS (
    SELECT * FROM {{ ref('dim_repositories') }}
),

fct_snaps AS (
    SELECT * FROM {{ ref('fct_repository_snapshots') }}
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY repository_id
        ORDER BY snapshot_timestamp DESC
    ) = 1
)

SELECT
    r.owner_login,
    COUNT(DISTINCT r.repository_id) AS total_repositories,
    SUM(s.stars_count) AS total_stars,
    ROUND(AVG(s.stars_count), 2) AS avg_stars,
    SUM(s.forks_count) AS total_forks,
    SUM(s.open_issues_count) AS total_open_issues,
    COUNT(DISTINCT COALESCE(r.language, 'Unknown')) AS distinct_languages_count,
    ARRAY_TO_STRING(ARRAY_AGG(DISTINCT COALESCE(r.language, 'Unknown') IGNORE NULLS), ', ') AS languages_list,
    COUNTIF(r.is_active) AS active_repositories_count,
    COUNTIF(r.is_archived) AS archived_repositories_count
FROM dim_repos r
JOIN fct_snaps s
    ON r.repository_id = s.repository_id
GROUP BY 1
ORDER BY total_repositories DESC, total_stars DESC;
