# NL-to-SQL Safety Rules

The backend must validate generated SQL before it reaches Snowflake.

## Allow

- A single `SELECT` statement, optionally with read-only CTEs (`WITH`).
- Only these fully qualified objects:
  - `FRAUD_DB.ANALYTICS.FRAUD_DAILY_SUMMARY`
  - `FRAUD_DB.ANALYTICS.AMOUNT_BUCKET_SUMMARY`
  - `FRAUD_DB.ANALYTICS.RISK_TIME_DASHBOARD`
  - `FRAUD_DB.ANALYTICS.ANALYST_REVIEW_QUEUE`
- Aggregations, filters, grouping, ordering, and a `LIMIT` clause.
- A maximum result size of 1,000 rows; default queue/detail queries to 100 rows.

## Reject

- More than one statement or any semicolon-separated commands.
- Any DDL/DML/administration keywords: `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `COPY`, `PUT`, `GET`, `CALL`, `GRANT`, `REVOKE`, `USE`.
- Any reference to `RAW`, Bronze, Silver, information schema, account usage, stages, or unapproved objects.
- Comments, file access, external functions, dynamic SQL, or stored-procedure calls.
- Requests that assert a person or transaction is definitely fraudulent.

## Application security

- Put Snowflake credentials only in the secure server-side environment/secrets manager.
- Use a least-privilege Snowflake role with `USAGE` on the warehouse/database/schema and `SELECT` only on the four approved Gold objects.
- Do not put a password, PAT, private key, AWS key, or database connection string in frontend code or in an uploaded context pack.
- Log question text, generated SQL, timestamp, user/session ID, execution outcome, and row count without storing sensitive credentials.
