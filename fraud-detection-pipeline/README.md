# Credit Card Fraud Detection Pipeline

An end-to-end data-engineering project that ingests the Kaggle ULB Credit Card Fraud dataset, processes it in Databricks, and publishes analyst-ready fraud-risk data in Snowflake.

## Architecture

`Kaggle CSV → AWS S3 → Databricks Bronze → Databricks Silver → Snowflake RAW → Snowflake ANALYTICS (Gold) → Analyst dashboard and demo`

**Orchestration:** Databricks Workflows.  
**Optional bonus:** a natural-language website that creates safe, read-only SQL queries against Snowflake Analytics.

## Repository layout

| Folder | Purpose |
| --- | --- |
| `s3/` | S3 bucket, upload, and folder-plan scripts (`landing/`, `archive/`, `reject/`) |
| `databricks/notebooks/` | Bronze and Silver Databricks notebooks |
| `databricks/src/` | Reusable PySpark transformation code |
| `snowflake/sql/` | RAW loading and Analytics/Gold SQL |
| `snowflake/models/` | Optional dbt models only |
| `orchestration/databricks_workflows/` | Databricks Workflows job definition and runbook |
| `tests/` | Data-quality and reconciliation tests |
| `docs/data-model/` | ERD, Mermaid flow, column definitions, and validation evidence |
| `config/` | Non-secret configuration templates |
| `scripts/` | Local helper scripts |

## Pipeline responsibilities

1. **S3:** place each source file in `landing/`; move successfully processed files to `archive/`; route invalid files to `reject/`.
2. **Bronze:** retain source values and add `ingestion_ts`, `source_file_name`, `batch_id`, and `load_date`.
3. **Silver:** validate/cast data, remove duplicates, create transaction and time features, retain `V1`–`V28`, and assign transparent rule-based risk features.
4. **Snowflake RAW:** load the enriched Silver data to `RAW.TRANSACTIONS`.
5. **Snowflake Analytics (Gold):** build `FRAUD_RISK_TRANSACTIONS`, `HIGH_RISK_QUEUE`, `FRAUD_DAILY_SUMMARY`, and `RISK_BAND_VALIDATION`.
6. **Workflow:** run ingestion, validation, transformation, load, analytics, reconciliation, and alerts in order.

## Security

Never commit CSV data, AWS keys, Databricks tokens, Snowflake passwords, or `.env` files. Use platform secret stores or local environment variables.

## Getting started

1. Create the S3 bucket and prefixes: `landing/`, `archive/`, `reject/`.
2. Add non-secret values to `config/example.env`.
3. Build and test Bronze, then Silver.
4. Configure Snowflake RAW and Analytics SQL.
5. Create and run the Databricks Workflow.

