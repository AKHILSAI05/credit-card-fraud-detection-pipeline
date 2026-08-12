# Databricks notebook source
# COMMAND ----------
# Bronze ingestion: S3 landing -> bronze.transactions_raw
# Creates/updates the file-level audit table: ops.processed_files
#
# Prerequisite: the Unity Catalog external location for this S3 path must pass
# the Databricks "Test connection" check.

# COMMAND ----------
dbutils.widgets.text("catalog_name", "workspace", "Unity Catalog name")
dbutils.widgets.text("batch_id", "batch_001", "Batch ID")
dbutils.widgets.text("source_file_name", "creditcard.csv", "Source file name")

catalog_name = dbutils.widgets.get("catalog_name").strip()
batch_id = dbutils.widgets.get("batch_id").strip()
source_file_name = dbutils.widgets.get("source_file_name").strip()

# Change this only when the input file name changes.
source_path = (
    "s3://intern-final-project-fraud-detection/landing/" + source_file_name
)

# A new ID is created for every notebook run and is kept on all Bronze rows.
import uuid
pipeline_run_id = str(uuid.uuid4())

BRONZE_SCHEMA = "bronze"
OPS_SCHEMA = "ops"
BRONZE_TABLE = f"{catalog_name}.{BRONZE_SCHEMA}.transactions_raw"
AUDIT_TABLE = f"{catalog_name}.{OPS_SCHEMA}.processed_files"

print(f"Source path: {source_path}")
print(f"Bronze table: {BRONZE_TABLE}")
print(f"Audit table: {AUDIT_TABLE}")

# COMMAND ----------
# If this cell fails, run `SHOW CATALOGS` in a SQL cell and replace the
# catalog_name widget value with a catalog that you can use.
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog_name}.{BRONZE_SCHEMA}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog_name}.{OPS_SCHEMA}")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
  source_file_name STRING,
  source_s3_uri STRING,
  batch_id STRING,
  pipeline_run_id STRING,
  status STRING,
  source_row_count BIGINT,
  bronze_row_count BIGINT,
  started_ts TIMESTAMP,
  completed_ts TIMESTAMP,
  error_message STRING
)
USING DELTA
""")

# COMMAND ----------
from delta.tables import DeltaTable
from pyspark.sql import functions as F
from pyspark.sql.types import LongType, StringType, StructField, StructType


def upsert_audit(status, source_row_count=None, bronze_row_count=None, error_message=None):
    """Write one current audit row for this file and batch."""
    audit_schema = StructType([
        StructField("source_file_name", StringType(), False),
        StructField("source_s3_uri", StringType(), False),
        StructField("batch_id", StringType(), False),
        StructField("pipeline_run_id", StringType(), False),
        StructField("status", StringType(), False),
        StructField("source_row_count", LongType(), True),
        StructField("bronze_row_count", LongType(), True),
        StructField("error_message", StringType(), True),
    ])

    update_df = (
        spark.createDataFrame(
            [(
                source_file_name, source_path, batch_id, pipeline_run_id, status,
                source_row_count, bronze_row_count, error_message,
            )],
            audit_schema,
        )
        .withColumn("started_ts", F.current_timestamp())
        .withColumn(
            "completed_ts",
            F.when(F.lit(status).isin("SUCCESS", "FAILED"), F.current_timestamp())
             .otherwise(F.lit(None).cast("timestamp")),
        )
    )

    (
        DeltaTable.forName(spark, AUDIT_TABLE)
        .alias("target")
        .merge(
            update_df.alias("source"),
            "target.source_file_name = source.source_file_name",
        )
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )


# Do not ingest a file that was already successfully processed.
already_processed = (
    spark.table(AUDIT_TABLE)
    .where(
        (F.col("source_file_name") == source_file_name)
        & (F.col("status") == "SUCCESS")
    )
    .limit(1)
    .count()
)

if already_processed:
    raise RuntimeError(
        f"SKIPPED: {source_file_name} already has SUCCESS in {AUDIT_TABLE}. "
        "Use a new corrected filename such as creditcard_batch_001_v2.csv."
    )

# COMMAND ----------
try:
    upsert_audit("RUNNING")

    # Read exactly one CSV batch from S3.
    source_df = (
        spark.read
        .option("header", "true")
        .option("inferSchema", "true")
        .csv(source_path)
    )
    source_row_count = source_df.count()

    # Standardize names and enforce the expected data types.
    # Source values remain unchanged; only technical standardization is performed.
    standardized_df = source_df.select(
        F.col("Time").cast("double").alias("time"),
        *[F.col(f"V{i}").cast("double").alias(f"v{i}") for i in range(1, 29)],
        F.col("Amount").cast("double").alias("amount"),
        F.col("Class").cast("int").alias("class"),
    )

    # Mentor instruction: remove identical duplicate source rows in Bronze.
    deduplicated_df = standardized_df.dropDuplicates()

    bronze_df = (
        deduplicated_df
        .withColumn("load_ts", F.current_timestamp())
        .withColumn("source_file", F.lit(source_file_name))
        .withColumn("source_s3_uri", F.lit(source_path))
        .withColumn("batch_id", F.lit(batch_id))
        .withColumn("ingestion_date", F.current_date())
        .withColumn("pipeline_run_id", F.lit(pipeline_run_id))
    )

    bronze_row_count = bronze_df.count()

    if source_row_count == 0:
        raise ValueError("The source file contains zero rows.")

    bronze_df.write.format("delta").mode("append").saveAsTable(BRONZE_TABLE)

    upsert_audit(
        "SUCCESS",
        source_row_count=source_row_count,
        bronze_row_count=bronze_row_count,
    )

    print(f"SUCCESS: Source rows = {source_row_count:,}")
    print(f"SUCCESS: Bronze rows after duplicate removal = {bronze_row_count:,}")
    print(f"Duplicate rows removed = {source_row_count - bronze_row_count:,}")

except Exception as exc:
    error_text = str(exc)[:4000]
    upsert_audit("FAILED", error_message=error_text)
    raise

# COMMAND ----------
# Validation / demo evidence
display(spark.table(BRONZE_TABLE).where(F.col("batch_id") == batch_id))
display(spark.table(AUDIT_TABLE).where(F.col("source_file_name") == source_file_name))
