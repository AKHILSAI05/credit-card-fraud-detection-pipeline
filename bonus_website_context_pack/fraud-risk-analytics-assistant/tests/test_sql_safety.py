import unittest

from python_app import validate_gold_sql
from production_app import correct_known_column_aliases


class SqlSafetyTests(unittest.TestCase):
    def test_corrects_review_queue_amount_bucket_alias(self):
        sql = "SELECT FRAUD_DB.ANALYTICS.ANALYST_REVIEW_QUEUE.AMOUNT_BUCKET FROM FRAUD_DB.ANALYTICS.ANALYST_REVIEW_QUEUE"
        corrected = correct_known_column_aliases(sql)
        self.assertIn("ANALYST_REVIEW_QUEUE.AMOUNT_RANGE", corrected)
        self.assertNotIn("ANALYST_REVIEW_QUEUE.AMOUNT_BUCKET", corrected)

    def test_allows_approved_select(self):
        sql = "SELECT TRANSACTION_DATE, TRANSACTION_COUNT FROM FRAUD_DB.ANALYTICS.FRAUD_DAILY_SUMMARY LIMIT 10"
        self.assertTrue(validate_gold_sql(sql)[0])

    def test_allows_read_only_cte(self):
        sql = "WITH DAILY AS (SELECT TRANSACTION_DATE, TRANSACTION_COUNT FROM FRAUD_DB.ANALYTICS.FRAUD_DAILY_SUMMARY) SELECT * FROM DAILY LIMIT 10"
        self.assertTrue(validate_gold_sql(sql)[0])

    def test_rejects_raw_object(self):
        self.assertFalse(validate_gold_sql("SELECT * FROM FRAUD_DB.RAW.TRANSACTIONS")[0])

    def test_rejects_unapproved_join(self):
        sql = "SELECT * FROM FRAUD_DB.ANALYTICS.FRAUD_DAILY_SUMMARY D JOIN FRAUD_DB.ANALYTICS.NOT_APPROVED N ON 1=1"
        self.assertFalse(validate_gold_sql(sql)[0])

    def test_rejects_multiple_statements(self):
        sql = "SELECT * FROM FRAUD_DB.ANALYTICS.FRAUD_DAILY_SUMMARY; SELECT 1"
        self.assertFalse(validate_gold_sql(sql)[0])

    def test_rejects_write_operation(self):
        self.assertFalse(validate_gold_sql("DELETE FROM FRAUD_DB.ANALYTICS.ANALYST_REVIEW_QUEUE")[0])

    def test_rejects_stage_and_system_access(self):
        sql = "SELECT SYSTEM$GET_PREDECESSOR_RETURN_VALUE() FROM FRAUD_DB.ANALYTICS.FRAUD_DAILY_SUMMARY"
        self.assertFalse(validate_gold_sql(sql)[0])


if __name__ == "__main__":
    unittest.main()
