-- Gold layer validation notebook (Snowflake SQL)
-- Set these values once per demo batch, then run each query.
USE WAREHOUSE FRAUD_WH;
USE DATABASE FRAUD_DB;

SET SELECTED_BATCH_ID = '<paste_batch_id_here>';
SET SELECTED_SOURCE_FILE = '<paste_source_file_name_here>';

-- 1. RAW ingestion validation: the selected batch must exist in Snowflake.
SELECT
    SOURCE_FILE,
    BATCH_ID,
    COUNT(*) AS RAW_TRANSACTION_COUNT,
    ROUND(SUM(AMOUNT), 2) AS RAW_TRANSACTION_AMOUNT,
    MIN(TRANSACTION_TIMESTAMP) AS FIRST_TRANSACTION_TIME,
    MAX(TRANSACTION_TIMESTAMP) AS LAST_TRANSACTION_TIME
FROM RAW.TRANSACTIONS
WHERE BATCH_ID = $SELECTED_BATCH_ID
  AND SOURCE_FILE = $SELECTED_SOURCE_FILE
GROUP BY SOURCE_FILE, BATCH_ID;

-- 2. Analyst review view reconciliation: every RAW transaction must be present once.
WITH raw_batch AS (
    SELECT COUNT(*) AS raw_row_count
    FROM RAW.TRANSACTIONS
    WHERE BATCH_ID = $SELECTED_BATCH_ID
      AND SOURCE_FILE = $SELECTED_SOURCE_FILE
), queue_batch AS (
    SELECT COUNT(*) AS queue_row_count
    FROM ANALYTICS.ANALYST_REVIEW_QUEUE
    WHERE REVIEW_TRANSACTION_ID IN (
        SELECT TRANSACTION_ID
        FROM RAW.TRANSACTIONS
        WHERE BATCH_ID = $SELECTED_BATCH_ID
          AND SOURCE_FILE = $SELECTED_SOURCE_FILE
    )
)
SELECT
    raw_row_count,
    queue_row_count,
    IFF(raw_row_count = queue_row_count, 'PASS', 'FAIL') AS queue_reconciliation_result
FROM raw_batch CROSS JOIN queue_batch;

-- 3. Validate that each Gold object was produced by the refresh procedure.
SELECT 'FRAUD_DAILY_SUMMARY' AS gold_object, COUNT(*) AS row_count
FROM ANALYTICS.FRAUD_DAILY_SUMMARY
UNION ALL
SELECT 'AMOUNT_BUCKET_SUMMARY', COUNT(*)
FROM ANALYTICS.AMOUNT_BUCKET_SUMMARY
UNION ALL
SELECT 'RISK_TIME_DASHBOARD', COUNT(*)
FROM ANALYTICS.RISK_TIME_DASHBOARD
UNION ALL
SELECT 'ANALYST_REVIEW_QUEUE', COUNT(*)
FROM ANALYTICS.ANALYST_REVIEW_QUEUE;

-- 4. Gold total reconciliation: daily Gold totals must equal Snowflake RAW totals.
WITH raw_total AS (
    SELECT COUNT(*) AS raw_transaction_count, ROUND(SUM(AMOUNT), 2) AS raw_transaction_amount
    FROM RAW.TRANSACTIONS
), gold_total AS (
    SELECT SUM(TRANSACTION_COUNT) AS gold_transaction_count,
           ROUND(SUM(TRANSACTION_AMOUNT), 2) AS gold_transaction_amount
    FROM ANALYTICS.FRAUD_DAILY_SUMMARY
)
SELECT
    raw_transaction_count,
    gold_transaction_count,
    raw_transaction_amount,
    gold_transaction_amount,
    IFF(raw_transaction_count = gold_transaction_count
        AND raw_transaction_amount = gold_transaction_amount, 'PASS', 'FAIL')
        AS gold_reconciliation_result
FROM raw_total CROSS JOIN gold_total;

-- 5. Review-priority distribution for the selected batch.
SELECT
    q.REVIEW_PRIORITY,
    COUNT(*) AS TRANSACTION_COUNT,
    ROUND(SUM(q.TRANSACTION_AMOUNT), 2) AS TRANSACTION_AMOUNT
FROM ANALYTICS.ANALYST_REVIEW_QUEUE q
JOIN RAW.TRANSACTIONS r
  ON q.REVIEW_TRANSACTION_ID = r.TRANSACTION_ID
WHERE r.BATCH_ID = $SELECTED_BATCH_ID
  AND r.SOURCE_FILE = $SELECTED_SOURCE_FILE
GROUP BY q.REVIEW_PRIORITY
ORDER BY CASE q.REVIEW_PRIORITY
    WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END;

-- 6. Top 100 review candidates: use this as live-demo evidence for the dashboard.
SELECT
    q.REVIEW_PRIORITY,
    q.REVIEW_TRANSACTION_ID,
    q.TRANSACTION_TIME,
    q.TRANSACTION_AMOUNT,
    q.AMOUNT_RANGE,
    q.TIME_SEGMENT,
    q.TIME_WINDOW,
    q.RAPID_REPEAT_INDICATOR,
    q.AMOUNT_DEVIATION_SCORE,
    q.AMOUNT_PERCENTILE_RANK
FROM ANALYTICS.ANALYST_REVIEW_QUEUE q
JOIN RAW.TRANSACTIONS r
  ON q.REVIEW_TRANSACTION_ID = r.TRANSACTION_ID
WHERE r.BATCH_ID = $SELECTED_BATCH_ID
  AND r.SOURCE_FILE = $SELECTED_SOURCE_FILE
ORDER BY CASE q.REVIEW_PRIORITY
    WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END,
    q.RAPID_REPEAT_INDICATOR DESC,
    q.AMOUNT_PERCENTILE_RANK DESC,
    q.TRANSACTION_TIME DESC
LIMIT 100;
