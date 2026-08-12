# Fraud Detection Bonus Website - Context Pack

This folder is prepared for building the optional Natural-Language-to-SQL website. It is separate from the current data pipeline and does not change any existing project files.

## What to upload to a website-building AI

Upload this entire folder, especially these files:

1. `01_Bonus_Website_Brief.md`
2. `02_Approved_Gold_Data_Model.md`
3. `03_NL_to_SQL_Safety_Rules.md`
4. `04_Website_Build_Prompt.md`
5. `architecture/fraud-detection-architecture-with-bonus.png`

The `reference/` folder provides project background only. It must not be treated as a source of credentials or live system access.

## Important security rule

Do not upload `.env` files, access keys, Databricks tokens, Snowflake passwords, or private connection strings. The website must use a secure backend and server-side secrets for any Snowflake connection.

## Website scope

The website is an optional bonus deliverable. It should let a user ask a plain-English analytics question, show the generated read-only SQL, execute it only against approved Snowflake Gold objects, show results, and offer a CSV download.
