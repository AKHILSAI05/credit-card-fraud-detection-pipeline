# Approved Snowflake Gold Data Model

The natural-language website may query only the following Gold objects in the `FRAUD_DB.ANALYTICS` schema.

## 1. FRAUD_DAILY_SUMMARY

One row per transaction date for executive and daily-operational reporting.

| Friendly concept | Column |
| --- | --- |
| Transaction Date | `TRANSACTION_DATE` |
| Transaction Count | `TRANSACTION_COUNT` |
| Total Transaction Amount | `TRANSACTION_AMOUNT` |
| Average / Minimum / Maximum Amount | `AVERAGE_TRANSACTION_AMOUNT`, `MINIMUM_TRANSACTION_AMOUNT`, `MAXIMUM_TRANSACTION_AMOUNT` |
| Historical Fraud / Legitimate Counts | `HISTORICAL_FRAUD_COUNT`, `HISTORICAL_LEGITIMATE_COUNT` |
| Historical Fraud Percentage | `HISTORICAL_FRAUD_PERCENTAGE` |
| High / Medium / Low Review Priority Counts | `HIGH_REVIEW_PRIORITY_COUNT`, `MEDIUM_REVIEW_PRIORITY_COUNT`, `LOW_REVIEW_PRIORITY_COUNT` |
| Rapid Repeat Count | `RAPID_REPEAT_COUNT` |

## 2. AMOUNT_BUCKET_SUMMARY

One row per amount range. Use it to compare volumes, value, review priorities, and historical labels across amount groups.

| Friendly concept | Column |
| --- | --- |
| Amount Range | `AMOUNT_RANGE` |
| Transaction Count / Amount / Average Amount | `TRANSACTION_COUNT`, `TRANSACTION_AMOUNT`, `AVERAGE_TRANSACTION_AMOUNT` |
| Historical Fraud Count | `HISTORICAL_FRAUD_COUNT` |
| High / Medium / Low Review Priority Counts | `HIGH_REVIEW_PRIORITY_COUNT`, `MEDIUM_REVIEW_PRIORITY_COUNT`, `LOW_REVIEW_PRIORITY_COUNT` |
| Rapid Repeat Count | `RAPID_REPEAT_COUNT` |

## 3. RISK_TIME_DASHBOARD

Aggregated risk and time analysis. Use it for charts by time segment, time window, amount bucket, and review priority.

| Friendly concept | Column |
| --- | --- |
| Time Segment | `TIME_SEGMENT` |
| Time Window | `TIME_WINDOW` |
| Amount Bucket | `AMOUNT_BUCKET` |
| Review Priority | `REVIEW_PRIORITY` |
| Transaction Count / Amount / Average Amount | `TRANSACTION_COUNT`, `TRANSACTION_AMOUNT`, `AVERAGE_TRANSACTION_AMOUNT` |
| Rapid Repeat Count | `RAPID_REPEAT_COUNT` |
| Historical Fraud Count | `HISTORICAL_FRAUD_COUNT` |

## 4. ANALYST_REVIEW_QUEUE

Transaction-level, analyst-facing queue. Use it for filtered detail tables only; default to a maximum of 100 rows.

| Friendly concept | Column |
| --- | --- |
| Review Transaction ID | `REVIEW_TRANSACTION_ID` |
| Transaction Time | `TRANSACTION_TIME` |
| Transaction Amount / Amount Range | `TRANSACTION_AMOUNT`, `AMOUNT_RANGE` |
| Time Segment / Time Window | `TIME_SEGMENT`, `TIME_WINDOW` |
| Rapid Repeat / Amount Outlier Indicators | `RAPID_REPEAT_INDICATOR`, `AMOUNT_OUTLIER_INDICATOR` |
| Amount Deviation / Percentile | `AMOUNT_DEVIATION_SCORE`, `AMOUNT_PERCENTILE_RANK` |
| Review Score / Review Priority | `REVIEW_SCORE`, `REVIEW_PRIORITY` |

## Analyst terminology

- **High, Medium, Low Review Priority:** order in which analysts should review operational signals; not confirmed fraud.
- **Rapid Repeat:** a transaction has another transaction close to it in the configured time window.
- **Amount Outlier:** amount is statistically unusual relative to the available dataset distribution.
- **Historical Fraud:** retrospective label from the source data, not a live prediction.
