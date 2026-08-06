-- Purpose: normalize Salesforce Opportunities for governed revenue analysis.
-- Grain: one row per Salesforce Opportunity id, including soft-deleted records.
SELECT
  Id AS opportunity_id,
  AccountId AS account_id,
  OwnerId AS owner_id,
  Name AS opportunity_name,
  StageName AS stage_name,
  Amount AS amount,
  Probability AS probability,
  CloseDate AS close_date,
  Type AS opportunity_type,
  LeadSource AS lead_source,
  ForecastCategoryName AS forecast_category,
  IsClosed AS is_closed,
  IsWon AS is_won,
  TIMESTAMP(CreatedDate) AS created_at,
  TIMESTAMP(LastModifiedDate) AS last_modified_at,
  TIMESTAMP(SystemModstamp) AS system_modified_at,
  IsDeleted AS is_deleted
FROM {{ ref('raw_salesforce_opportunities') }}
