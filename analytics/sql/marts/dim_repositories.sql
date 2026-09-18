-- =============================================================================
-- Model: dim_repositories
-- Layer: Marts (Dimensional)
-- Dialect: Google Cloud BigQuery
-- Description: Conformed repository dimension table for BI, reporting,
--              and analytics dashboarding. Contains latest attributes and statuses.
-- Cluster By: language, visibility, owner_login
-- =============================================================================

WITH repository_activity AS (
    SELECT * FROM {{ ref('int_repository_activity') }}
)

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
    html_url,
    created_at,
    updated_at,
    pushed_at AS last_pushed_at,
    days_since_creation,
    days_since_last_push,
    days_between_creation_and_last_push,
    activity_status,
    is_active,
    size_category,
    extracted_at AS last_synced_at
FROM repository_activity;
