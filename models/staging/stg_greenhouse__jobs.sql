-- Purpose: clean published Greenhouse jobs for downstream analysis.
-- Grain: one row per published job.
-- Cadence: daily.
-- Source: raw.greenhouse_job_board_jobs.
WITH source AS (
  SELECT
    id,
    internal_job_id,
    title,
    company_name,
    location.name AS location_name,
    absolute_url,
    language,
    first_published,
    updated_at
  FROM {{ ref('raw_greenhouse_job_board_jobs') }}
)

SELECT
  CAST(id AS STRING) AS job_id,
  CAST(internal_job_id AS STRING) AS internal_job_id,
  title,
  company_name,
  location_name,
  absolute_url,
  language,
  first_published,
  updated_at
FROM source
