-- Purpose: normalize Salesforce Users for durable historical ownership dimensions.
-- Grain: one row per Salesforce User id, including inactive users.
SELECT
  Id AS user_id,
  Name AS user_name,
  Alias AS user_alias,
  UserType AS user_type,
  ProfileId AS profile_id,
  IsActive AS is_active,
  TIMESTAMP(CreatedDate) AS created_at,
  TIMESTAMP(LastModifiedDate) AS last_modified_at,
  TIMESTAMP(SystemModstamp) AS system_modified_at
FROM {{ ref('raw_salesforce_users') }}
