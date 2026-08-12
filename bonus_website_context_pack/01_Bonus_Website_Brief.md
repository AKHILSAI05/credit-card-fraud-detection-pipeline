# Bonus Website Brief: Natural Language Analytics Assistant

## Objective

Build a professional, read-only analytics website for the Credit Card Fraud Detection data-engineering project. A user asks questions in plain English. The system converts the question into safe Snowflake SQL, queries approved Gold analytics objects, and displays the results as a table, chart, and downloadable CSV.

## Business purpose

The data pipeline creates operational review priorities from transaction behaviour such as rapid repeats, amount outliers, transaction time, and repeated anonymized patterns. The website makes those curated analytics easier for an analyst or reviewer to explore without writing SQL manually.

## Critical business disclaimer

`Review Priority` is an operational queue priority, not a confirmed fraud decision. `Fraud Label` is historical source-label information used for retrospective validation only; it must never be used by the website to claim that the system predicted fraud.

## Approved flow

```text
User question
  -> website interface
  -> AI SQL generation
  -> SQL safety validation
  -> secure backend with server-side Snowflake credentials
  -> approved Snowflake Gold objects only
  -> table/chart/downloadable result
```

## Required capabilities

- Plain-English question input with example questions.
- Show the generated SQL before or alongside the result.
- Execute only validated, read-only SQL.
- Use only approved objects in `FRAUD_DB.ANALYTICS`.
- Present a readable table and an appropriate chart when results are aggregations.
- Offer a CSV download of returned results.
- Include a clear/reset button that removes filters and results.
- Use friendly labels: no database-style underscores in visible headings.
- Include a visible disclaimer about Review Priority.

## Example questions

- Show daily transaction count and transaction amount.
- Which amount range has the most high-review-priority transactions?
- Show high-review-priority transactions in the Early Morning time window.
- Compare review-priority counts by time segment.
- Show the 20 most recent transactions that need high-priority review.
- What percentage of transactions had a historical fraud label each day?

## Out of scope

- Do not query Bronze, Silver, or Raw tables.
- Do not insert, update, delete, merge, create, alter, drop, or call procedures.
- Do not expose any secrets in browser code, prompts, logs, downloads, or screenshots.
- Do not train a fraud model or call Review Priority a fraud prediction.
