-- Purpose: deterministic company model for the owned HubSpot proof account.
-- Grain: one row per HubSpot company id.
WITH source AS (
  SELECT
    CAST(id AS STRING) AS company_id,
    properties.name AS company_name,
    properties.domain AS domain,
    TIMESTAMP(createdAt) AS created_at,
    TIMESTAMP(updatedAt) AS updated_at,
    CAST(archived AS BOOL) AS archived
  FROM {{ ref('raw_hubspot_test_companies') }}
)

SELECT
  company_id,
  company_name,
  domain,
  created_at,
  updated_at,
  archived
FROM source
