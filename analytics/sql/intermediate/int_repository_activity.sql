-- =============================================================================
-- Model: int_repository_activity
-- Layer: Intermediate / Normalized Analytics
-- Dialect: Google Cloud BigQuery
-- Description: Enriches staging repository records with derived temporal metrics,
--              activity classifications, technical ratios, and popularity scores.
-- Granularity: One row per repository
-- =============================================================================

WITH staging AS (
    SELECT * FROM {{ ref('stg_github_repositories') }}
),

enriched AS (
    SELECT
        repository_surrogate_key,
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
        extracted_at,
        stars_count,
        forks_count,
        open_issues_count,
        subscribers_count,
        size_kb,
        html_url,

        -- 1. Temporal spans (deterministic relative to ingestion timestamp)
        TIMESTAMP_DIFF(extracted_at, created_at, DAY) AS days_since_creation,
        CASE
            WHEN pushed_at IS NOT NULL
            THEN GREATEST(0, TIMESTAMP_DIFF(extracted_at, pushed_at, DAY))
            ELSE NULL
        END AS days_since_last_push,
        CASE
            WHEN pushed_at IS NOT NULL
            THEN GREATEST(0, TIMESTAMP_DIFF(pushed_at, created_at, DAY))
            ELSE NULL
        END AS days_between_creation_and_last_push,

        -- 2. Size classification
        CASE
            WHEN size_kb = 0 THEN 'EMPTY'
            WHEN size_kb <= 100 THEN 'MICRO'
            WHEN size_kb <= 10000 THEN 'SMALL'
            WHEN size_kb <= 100000 THEN 'MEDIUM'
            ELSE 'LARGE'
        END AS size_category,

        -- 3. Technical & Engagement Ratios (zero-division safe)
        ROUND(SAFE_DIVIDE(forks_count, stars_count), 4) AS fork_to_star_ratio,
        ROUND(SAFE_DIVIDE(open_issues_count, stars_count), 4) AS issue_to_star_ratio,
        ROUND(SAFE_DIVIDE(stars_count, forks_count), 4) AS star_to_fork_ratio,

        -- 4. Standardized popularity composite index
        ROUND(
            (stars_count * 1.0) + (forks_count * 2.0) + (subscribers_count * 1.5),
            2
        ) AS community_interest_score

    FROM staging
)

SELECT
    *,
    -- 5. Activity Status Categorization
    CASE
        WHEN is_disabled THEN 'DISABLED'
        WHEN is_archived THEN 'ARCHIVED'
        WHEN pushed_at IS NULL THEN 'INACTIVE'
        WHEN days_since_last_push <= 90 THEN 'ACTIVE'
        WHEN days_since_last_push <= 180 THEN 'STALE'
        ELSE 'INACTIVE'
    END AS activity_status,

    -- Boolean flag for quick filtering
    CASE
        WHEN NOT is_disabled
             AND NOT is_archived
             AND pushed_at IS NOT NULL
             AND days_since_last_push <= 90
        THEN TRUE
        ELSE FALSE
    END AS is_active

FROM enriched;
