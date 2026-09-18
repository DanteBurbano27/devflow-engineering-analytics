-- Validation Suite for BigQuery Analytics

-- 1. Check for Duplicate Primary Keys
SELECT
    repository_id,
    COUNT(*) as duplicate_count
FROM `devflow.analytics.dim_repositories`
GROUP BY repository_id
HAVING COUNT(*) > 1;

-- 2. Check for Negative Metrics
SELECT
    repository_id
FROM `devflow.analytics.fct_repository_snapshots`
WHERE stars_count < 0
   OR forks_count < 0
   OR size_kb < 0;

-- 3. Check for Nulls in Required Fields
SELECT
    repository_id
FROM `devflow.analytics.dim_repositories`
WHERE repository_name IS NULL
   OR full_name IS NULL
   OR visibility IS NULL;
