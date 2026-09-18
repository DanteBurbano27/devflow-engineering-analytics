-- =============================================================================
-- Model: stg_github_repositories
-- Layer: Staging
-- Dialect: Google Cloud BigQuery
-- Description: Cleans and casts raw ingested GitHub repository snapshots.
-- Granularity: One row per repository extraction snapshot
-- =============================================================================

WITH raw_source AS (
    SELECT
        CAST(repository_id AS INT64) AS repository_id,
        TRIM(CAST(repository_name AS STRING)) AS repository_name,
        TRIM(CAST(full_name AS STRING)) AS full_name,
        TRIM(CAST(owner_login AS STRING)) AS owner_login,
        TRIM(CAST(description AS STRING)) AS description,
        LOWER(TRIM(CAST(visibility AS STRING))) AS visibility,
        TRIM(CAST(default_branch AS STRING)) AS default_branch,
        COALESCE(TRIM(CAST(language AS STRING)), 'Unknown') AS language,
        CAST(is_fork AS BOOL) AS is_fork,
        CAST(is_archived AS BOOL) AS is_archived,
        CAST(is_disabled AS BOOL) AS is_disabled,
        CAST(created_at AS TIMESTAMP) AS created_at,
        CAST(updated_at AS TIMESTAMP) AS updated_at,
        CAST(pushed_at AS TIMESTAMP) AS pushed_at,
        CAST(stars_count AS INT64) AS stars_count,
        CAST(forks_count AS INT64) AS forks_count,
        CAST(open_issues_count AS INT64) AS open_issues_count,
        CAST(subscribers_count AS INT64) AS subscribers_count,
        CAST(size_kb AS INT64) AS size_kb,
        TRIM(CAST(html_url AS STRING)) AS html_url,
        CAST(extracted_at AS TIMESTAMP) AS extracted_at
    FROM
        {{ source('raw_github', 'repositories') }}
    WHERE
        repository_id IS NOT NULL
        AND repository_id > 0
        AND full_name IS NOT NULL
        AND LENGTH(TRIM(full_name)) > 0
)

SELECT
    -- Stable repository identity; extracted_at remains the snapshot identity.
    FARM_FINGERPRINT(
        CONCAT(CAST(repository_id AS STRING), '|', full_name)
    ) AS repository_surrogate_key,
    repository_id,
    repository_name,
    full_name,
    owner_login,
    description,
    visibility,
    default_branch,
    language,
    is_fork,
    is_archived,
    is_disabled,
    created_at,
    updated_at,
    pushed_at,
    stars_count,
    forks_count,
    open_issues_count,
    subscribers_count,
    size_kb,
    html_url,
    extracted_at
FROM raw_source;
