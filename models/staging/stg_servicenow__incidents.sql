-- Purpose: normalize ServiceNow incidents for operational analysis.
-- Grain: one row per ServiceNow incident sys_id returned by the current full read.
WITH source AS (
  SELECT
    sys_id AS incident_id,
    number AS incident_number,
    short_description,
    description,
    SAFE_CAST(state AS INT64) AS state,
    SAFE_CAST(priority AS INT64) AS priority,
    CASE
      WHEN LOWER(active) = 'true' THEN TRUE
      WHEN LOWER(active) = 'false' THEN FALSE
      ELSE NULL
    END AS is_active,
    SAFE.PARSE_TIMESTAMP('%F %H:%M:%S', NULLIF(opened_at, '')) AS opened_at,
    SAFE.PARSE_TIMESTAMP('%F %H:%M:%S', NULLIF(resolved_at, '')) AS resolved_at,
    SAFE.PARSE_TIMESTAMP('%F %H:%M:%S', NULLIF(closed_at, '')) AS closed_at,
    PARSE_TIMESTAMP('%F %H:%M:%S', sys_created_on) AS created_at,
    PARSE_TIMESTAMP('%F %H:%M:%S', sys_updated_on) AS updated_at,
    sys_updated_by AS updated_by
  FROM {{ ref('raw_servicenow_incidents') }}
)

SELECT
  incident_id,
  incident_number,
  short_description,
  description,
  state,
  priority,
  is_active,
  opened_at,
  resolved_at,
  closed_at,
  created_at,
  updated_at,
  updated_by
FROM source
