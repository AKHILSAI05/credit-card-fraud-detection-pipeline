"""Logical data assets shown in Dagster's lineage graph.

These are external assets: Dagster orchestrates their updates through the job
but does not independently materialize them from the Lineage page.
"""

import dagster as dg


s3_landing_files = dg.AssetSpec(
    key=dg.AssetKey(["aws_s3", "landing_creditcard_files"]),
    group_name="01_ingestion",
    description="New CSV files placed in s3://intern-final-project-fraud-detection/landing/.",
)

s3_archived_files = dg.AssetSpec(
    key=dg.AssetKey(["aws_s3", "archive", "processed_creditcard_files"]),
    deps=[s3_landing_files.key],
    group_name="01_ingestion",
    description=(
        "Landing files copied to archive/ only after Bronze, Silver, Snowflake RAW "
        "validation, and Gold refresh all succeed."
    ),
)

s3_rejected_files = dg.AssetSpec(
    key=dg.AssetKey(["aws_s3", "reject", "duplicate_content_files"]),
    deps=[s3_landing_files.key],
    group_name="01_ingestion",
    description=(
        "Files routed to reject/duplicates/ because their SHA-256 content hash "
        "matches a file that already completed Bronze successfully."
    ),
)

bronze_transactions = dg.AssetSpec(
    key=dg.AssetKey(["databricks", "bronze", "raw_transactions"]),
    deps=[s3_landing_files.key],
    group_name="02_databricks",
    description=(
        "Databricks Bronze raw transaction table. Includes source lineage and audit fields."
    ),
)

silver_transactions = dg.AssetSpec(
    key=dg.AssetKey(["databricks", "silver", "transactions_silver"]),
    deps=[bronze_transactions.key],
    group_name="02_databricks",
    description=(
        "Validated and enriched transaction data. Audit columns are inherited from Bronze."
    ),
)

snowflake_raw_transactions = dg.AssetSpec(
    key=dg.AssetKey(["snowflake", "raw", "transactions"]),
    deps=[silver_transactions.key],
    group_name="03_snowflake",
    description="Snowflake RAW staging copy of the completed Databricks Silver batch.",
)

gold_analytics = dg.AssetSpec(
    key=dg.AssetKey(["snowflake", "analytics", "fraud_reporting"]),
    deps=[snowflake_raw_transactions.key],
    group_name="03_snowflake",
    description=(
        "Gold reporting outputs: daily summary, amount-bucket summary, risk/time dashboard, "
        "and the analyst review queue. Audit columns are excluded."
    ),
)

native_streamlit_dashboard = dg.AssetSpec(
    key=dg.AssetKey(["snowflake", "streamlit", "fraud_risk_dashboard"]),
    deps=[gold_analytics.key],
    group_name="04_consumption",
    description="Native Snowflake Streamlit dashboard consuming only Gold analytics objects.",
)


all_assets = [
    s3_landing_files,
    s3_archived_files,
    s3_rejected_files,
    bronze_transactions,
    silver_transactions,
    snowflake_raw_transactions,
    gold_analytics,
    native_streamlit_dashboard,
]
