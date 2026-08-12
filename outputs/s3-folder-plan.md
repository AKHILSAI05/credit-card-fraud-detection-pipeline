# S3 Folder Plan — Credit Card Fraud Detection

## Bucket

Use one project bucket, replacing the placeholder below after the team confirms the AWS account and region:

```text
fraud-detection-<team-name>-<aws-account-id>-<region>
```

Example:

```text
fraud-detection-team1-123456789012-ap-south-1
```

## Required Prefixes

```text
s3://<bucket>/
├── landing/
│   └── creditcard.csv               # Original Kaggle source file
├── archive/                         # Source files after a successful load
├── rejects/
│   ├── bronze/                      # Schema or ingestion rejects
│   └── silver/                      # Cleaning/validation rejects
├── checkpoints/
│   └── bronze/                      # Databricks Auto Loader/stream checkpoints
├── exports/
│   └── silver/                      # Enriched data exports for Snowflake, if staging through S3
└── logs/                            # Optional workflow/audit log exports
```

## Pipeline Usage

| Prefix | Pipeline use | Owner | Retention guidance |
|---|---|---|---|
| `landing/` | New CSV source files waiting for Databricks ingestion | Ingestion owner | Keep until successful processing is evidenced |
| `archive/` | Successfully ingested source files | Ingestion owner | Keep for audit/replay |
| `rejects/bronze/` | Records/files failing ingestion or schema checks | Bronze owner | Keep with failure reason and batch ID |
| `rejects/silver/` | Records failing Silver quality rules | Silver owner | Keep with failure reason and batch ID |
| `checkpoints/bronze/` | Databricks processing state | Databricks owner | Do not manually delete during active development |
| `exports/silver/` | Files staged for Snowflake `COPY INTO`, if used | Snowflake owner | Archive after successful load/reconciliation |
| `logs/` | Optional exported workflow logs | Orchestration owner | Keep through final assessment |

## First File Upload

Upload the Kaggle file as:

```text
s3://<bucket>/landing/creditcard.csv
```

Record the source file row count and file checksum in the project README before the first Bronze run.

## Security Rules

- Block public access on the bucket.
- Enable default server-side encryption.
- Use least-privilege IAM roles for Databricks and team members.
- Store access keys/credentials only in Databricks Secrets or AWS Secrets Manager.
- Do not store secrets, credentials, or personal data in Git.

## Naming Rules

- Use lowercase prefix names.
- Keep the original source file unchanged in `landing/` until it is archived.
- Append a batch ID or date to repeat uploads, for example `creditcard_2026-07-29.csv`.
- Include batch ID and rejection reason in rejected-output file names.
