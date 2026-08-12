# Dagster Credit Fraud Orchestration

This project orchestrates:

`S3 landing → Databricks Bronze → Databricks Silver → Snowflake RAW → Snowflake Gold`

## Design rules

- Each S3 file is identified by object key and ETag.
- The Databricks Bronze job checks `workspace.ops.processed_files` before ingestion.
- Bronze adds audit fields; Silver carries them unchanged; Snowflake RAW retains them.
- Gold selects only business columns and does not contain audit fields.
- Secrets use environment variables or a secrets manager, never source code or Git.

## Local setup

```powershell
cd orchestration/dagster_creditfraud
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
dagster dev -m dagster_creditfraud.definitions
```

Copy `.env.example` to `.env` and fill values before starting the service. The S3 sensor is stopped by default.

## Activation order

1. Run `sql/refresh_fraud_gold.sql` in Snowflake. It creates the procedure Dagster calls after every successful RAW load.
2. Create the Bronze, Silver, and Silver-to-Snowflake Databricks Jobs. Each notebook task must accept `source_file_name`, `batch_id`, and `catalog_name` with Databricks widgets.
3. Copy `.env.example` to `.env`, then add the Job IDs and local secrets. `.env` is ignored by Git.
4. Start Dagster and launch one manual run with a test batch. Confirm no failed runs and validate Gold with `sql/validate_gold.sql`.
5. Only then enable `landing_file_sensor` and demonstrate duplicate-file skip.

## Pipeline failure notifications

`pipeline_failure_reject_sensor` handles final job failures after retries. It
moves a valid landing file to `reject/validation_failed/` and can publish one
Amazon SNS notification for the failed run. An SNS email subscription receives
that notification as an email alert.

Set these values in `.env` (never commit them):

```text
SNS_FAILURE_TOPIC_ARN=arn:aws:sns:ap-south-1:<account-id>:fraud-pipeline-failure-alerts
```

The Dagster execution role/user needs `sns:Publish` for this topic. Confirm the
email subscription in SNS, then set the topic ARN in `.env`. Leave the variable
empty to disable notifications while preserving the existing failure-file
routing behavior.
