# Prompt for a Website-Building AI

Build a polished, responsive website named **Fraud Risk Analytics Assistant** for a credit-card fraud data-engineering capstone. This is an analytics and review-prioritization interface, not a fraud-prediction model.

Create a dark, modern operations-dashboard style with accessible contrast, compact cards, subtle blue/purple accents, clear typography, and friendly business labels without underscores.

## Required layout

1. **Header:** title, short subtitle, and a disclaimer: “Review Priority is an operational review queue, not a confirmed fraud decision.”
2. **Question panel:** plain-English text input, submit button, clear button, and 4–6 clickable example questions.
3. **Result summary cards:** returned rows, selected data source, query status, and result freshness.
4. **Generated SQL:** a collapsible, read-only panel that shows validated SQL.
5. **Result area:** responsive data table, CSV download button, and a chart chosen based on result shape (bar for categorical comparison, line for dates, table for detailed queue results).
6. **Safe data-source selector:** Daily Overview, Amount Analysis, Risk and Time Analysis, Analyst Review Queue.
7. **Analyst Review queue filters:** Review Priority, Time Segment, Time Window, Amount Range, minimum transaction amount, maximum transaction amount, transaction-date range, and transaction ID search.

## Data and security behaviour

- The user interface must never contain credentials or a direct Snowflake connection string.
- Implement a placeholder secure backend API layer: `POST /api/query` takes the natural-language question and optional filters, generates/receives SQL, validates it, executes it server-side, and returns safe results.
- The backend permits only one read-only SELECT/CTE query and only approved objects in `FRAUD_DB.ANALYTICS`.
- Reject DDL/DML and raw/bronze/silver access.
- Default detail results to `LIMIT 100`; never return more than 1,000 rows.
- Explain errors in plain language without exposing system internals or secrets.

## Approved Gold objects

- `FRAUD_DAILY_SUMMARY`: daily transaction volumes, amounts, review-priority totals, and historical validation counts.
- `AMOUNT_BUCKET_SUMMARY`: comparisons by amount range.
- `RISK_TIME_DASHBOARD`: analysis by time segment, time window, amount bucket, and review priority.
- `ANALYST_REVIEW_QUEUE`: transaction-level queue with review priority, transaction amount/time, rapid-repeat indicator, amount-outlier indicator, score, and percentile.

## Example user prompts

- “Show daily transaction amount and transaction count.”
- “Which amount range has the highest count of high-review-priority transactions?”
- “Show the 20 most recent high-review-priority transactions in the Early Morning time window.”
- “Compare review priorities by time segment.”

Add clear empty states, loading states, error states, a reset interaction, and a simple audit-log panel placeholder that states the query is logged safely on the server.
