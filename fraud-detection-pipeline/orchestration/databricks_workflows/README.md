# Databricks Workflow

The required job sequence is:

1. Detect new file in S3 `landing/`
2. Ingest Bronze
3. Validate Bronze
4. Transform Silver
5. Validate Silver
6. Load Snowflake RAW
7. Build Snowflake Analytics/Gold
8. Reconcile counts and publish success/failure status

Configure retries and alerts for all critical tasks.

