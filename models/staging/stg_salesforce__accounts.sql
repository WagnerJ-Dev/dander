-- Purpose: normalize Salesforce Accounts for CRM and revenue analysis.
-- Grain: one row per Salesforce Account id, including soft-deleted records.
WITH source AS (
  SELECT
    Id AS account_id,
    Name AS account_name,
    OwnerId AS owner_id,
    ParentId AS parent_account_id,
    Type AS account_type,
    Industry AS industry,
    AnnualRevenue AS annual_revenue,
    NumberOfEmployees AS number_of_employees,
    Website AS website,
    Phone AS phone,
    BillingCity AS billing_city,
    BillingState AS billing_state,
    BillingPostalCode AS billing_postal_code,
    BillingCountry AS billing_country,
    TIMESTAMP(CreatedDate) AS created_at,
    TIMESTAMP(LastModifiedDate) AS last_modified_at,
    TIMESTAMP(SystemModstamp) AS system_modified_at,
    IsDeleted AS is_deleted
  FROM {{ ref('raw_salesforce_accounts') }}
)

SELECT
  account_id,
  account_name,
  owner_id,
  parent_account_id,
  account_type,
  industry,
  annual_revenue,
  number_of_employees,
  website,
  phone,
  billing_city,
  billing_state,
  billing_postal_code,
  billing_country,
  created_at,
  last_modified_at,
  system_modified_at,
  is_deleted
FROM source
