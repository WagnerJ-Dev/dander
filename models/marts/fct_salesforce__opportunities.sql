-- Purpose: governed Salesforce opportunity facts with Account and historical owner dimensions.
-- Grain: one non-deleted Opportunity whose Account is either present and active or not assigned.
WITH users AS (
  SELECT * FROM {{ ref('stg_salesforce__users') }}
),
accounts AS (
  SELECT * FROM {{ ref('stg_salesforce__accounts') }} WHERE NOT is_deleted
),
opportunities AS (
  SELECT * FROM {{ ref('stg_salesforce__opportunities') }} WHERE NOT is_deleted
)

SELECT
  opportunity.opportunity_id,
  opportunity.opportunity_name,
  opportunity.account_id,
  account.account_name,
  account.account_type,
  account.industry,
  opportunity.owner_id,
  owner.user_name AS owner_name,
  owner.user_alias AS owner_alias,
  owner.user_type AS owner_type,
  owner.is_active AS owner_is_active,
  opportunity.stage_name,
  opportunity.amount,
  opportunity.probability,
  opportunity.close_date,
  opportunity.opportunity_type,
  opportunity.lead_source,
  opportunity.forecast_category,
  opportunity.is_closed,
  opportunity.is_won,
  opportunity.created_at,
  opportunity.last_modified_at,
  opportunity.system_modified_at
FROM opportunities AS opportunity
LEFT JOIN accounts AS account ON opportunity.account_id = account.account_id
LEFT JOIN users AS owner ON opportunity.owner_id = owner.user_id
WHERE opportunity.account_id IS NULL OR account.account_id IS NOT NULL
