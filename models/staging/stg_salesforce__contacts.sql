-- Purpose: normalize Salesforce Contacts while preserving soft-deletion state.
-- Grain: one row per Salesforce Contact id.
SELECT
  Id AS contact_id,
  AccountId AS account_id,
  OwnerId AS owner_id,
  FirstName AS first_name,
  LastName AS last_name,
  Name AS contact_name,
  Email AS email,
  Phone AS phone,
  Title AS title,
  Department AS department,
  MailingCity AS mailing_city,
  MailingState AS mailing_state,
  MailingPostalCode AS mailing_postal_code,
  MailingCountry AS mailing_country,
  TIMESTAMP(CreatedDate) AS created_at,
  TIMESTAMP(LastModifiedDate) AS last_modified_at,
  TIMESTAMP(SystemModstamp) AS system_modified_at,
  IsDeleted AS is_deleted
FROM {{ ref('raw_salesforce_contacts') }}
