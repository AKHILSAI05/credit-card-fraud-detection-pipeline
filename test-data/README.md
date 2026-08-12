# Pipeline Failure Notification Demo Files

These files are deliberately invalid CSV inputs for demonstrating the Dagster final-failure workflow and Amazon SNS email alert.

## Use

1. Ensure the Dagster landing-file sensor and `pipeline_failure_reject_sensor` are running.
2. Upload **one** file to the S3 landing prefix:

   ```text
   s3://intern-final-project-fraud-detection/landing/
   ```

3. Wait for the pipeline run to reach final `FAILURE` status after its configured retries.
4. Confirm the file is routed to:

   ```text
   s3://intern-final-project-fraud-detection/reject/validation_failed/
   ```

5. Confirm the SNS email subject starts with:

   ```text
   [Action required] Dagster pipeline failed:
   ```

## Demo files

| File | Intentional issue |
|---|---|
| `demo_invalid_schema_missing_required_columns.csv` | Has no required transaction columns |
| `demo_invalid_schema_unexpected_columns.csv` | Uses unsupported descriptive columns |
| `demo_invalid_schema_partial_transaction_columns.csv` | Contains only part of the expected transaction schema |

Do not upload more than one demo file at a time. Use a new filename or alter non-sensitive content if duplicate-content detection routes a repeat upload to `reject/duplicates/` instead of running the pipeline.

These files contain no production data and are safe to keep in source control.
