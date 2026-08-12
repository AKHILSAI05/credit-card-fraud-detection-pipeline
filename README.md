# Credit Card Fraud Detection Pipeline

An end-to-end, governed fraud-risk analytics project. It ingests transaction files through AWS S3 and Dagster, transforms them through Databricks Bronze/Silver and Snowflake RAW/Gold layers, provides a Snowflake Streamlit dashboard and a secure natural-language analytics website, and sends operational email alerts for final pipeline failures.

## Components

| Component | Location | Purpose |
|---|---|---|
| Pipeline SQL and notebooks | `databricks/`, `snowflake/`, `fraud-detection-pipeline/` | Bronze, Silver, RAW, Gold processing |
| Orchestration | `orchestration/dagster_creditfraud/` | S3 sensors, Databricks runs, Snowflake steps, duplicate handling, reject routing |
| Failure email alerts | `orchestration/dagster_creditfraud/src/dagster_creditfraud/sensors.py` | Final Dagster-failure alert through Amazon SNS |
| Streamlit dashboard | `streamlit/streamlit_app.py` | Snowflake Native operational fraud review dashboard |
| Bonus website | `bonus_website_context_pack/fraud-risk-analytics-assistant/` | Safe natural-language analytics website backed by approved Gold data |
| Documentation | `docs/`, `bonus_website_context_pack/`, component READMEs | Architecture, data model, operation, and website guidance |

## Architecture

```text
S3 landing files
  → Dagster orchestration
  → Databricks Bronze / Silver
  → Snowflake RAW / Gold
  → Streamlit dashboard and Fraud Risk Analytics Assistant

Final pipeline failure
  → Dagster failure sensor
  → S3 reject/validation_failed/
  → Amazon SNS topic
  → subscribed operational email inbox
```

## Key safeguards

- The Dagster failure sensor only alerts after the run reaches final `FAILURE` status, after configured retries.
- SNS publishing is scoped to one topic with least-privilege IAM permission.
- The bonus website permits only validated, read-only SQL against approved Snowflake Gold objects.
- Browser code never contains Snowflake credentials, private keys, or Gemini keys.
- Full raw datasets, local environments, logs, and real `.env` files are excluded from this repository.

## Setup references

- [Dagster orchestration](orchestration/dagster_creditfraud/README.md)
- [Bonus website](bonus_website_context_pack/fraud-risk-analytics-assistant/README.md)
- [Approved Gold data model](bonus_website_context_pack/02_Approved_Gold_Data_Model.md)
- [Natural-language-to-SQL safety rules](bonus_website_context_pack/03_NL_to_SQL_Safety_Rules.md)
- [S3 folder plan](docs/s3-folder-plan.md)

## Before running

1. Copy the appropriate `.env.example` file to `.env` locally.
2. Provide valid AWS, Databricks, Snowflake, and Gemini settings only on the runtime machine.
3. Never commit secrets, private-key files, or production datasets.
4. Configure `SNS_FAILURE_TOPIC_ARN` and an SNS email subscription if pipeline failure alerts are required.

