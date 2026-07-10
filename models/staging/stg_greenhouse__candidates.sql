-- Purpose: cleaned staging model for Greenhouse candidates.
-- Grain:   one row per candidate.
-- Cadence: daily.
-- Source:  raw.greenhouse_candidates.
WITH source AS (
  SELECT
    id,
    first_name,
    last_name,
    updated_at
  FROM {{ ref('raw_greenhouse_candidates') }}
)

SELECT
  CAST(id AS STRING) AS candidate_id,  -- keep ids as STRING (inference trap)
  first_name,
  last_name,
  updated_at
FROM source
