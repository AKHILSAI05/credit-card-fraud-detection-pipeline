import os
from urllib.parse import urlparse

import boto3
import dagster as dg

from .assets import (
    bronze_transactions,
    gold_analytics,
    native_streamlit_dashboard,
    s3_archived_files,
    s3_landing_files,
    silver_transactions,
    snowflake_raw_transactions,
)
from .resources import execute_gold_refresh, get_snowflake_raw_batch_count, run_databricks_job
from .settings import required_env


RETRY_POLICY = dg.RetryPolicy(max_retries=2, delay=30)


@dg.op(
    config_schema={
        "catalog_name": str,
        "source_file_name": str,
        "source_path": str,
        "batch_id": str,
        # These are supplied by the S3 sensor. Defaults keep a controlled
        # manual Databricks Job run possible for troubleshooting.
        "content_sha256": dg.Field(str, is_required=False, default_value=""),
        "source_etag": dg.Field(str, is_required=False, default_value=""),
        "file_size_bytes": dg.Field(str, is_required=False, default_value=""),
    },
    retry_policy=RETRY_POLICY,
)
def run_bronze(context: dg.OpExecutionContext) -> int:
    """Bronze performs the processed-file audit check before reading the file."""
    run_id = run_databricks_job(
        required_env("DATABRICKS_BRONZE_JOB_ID"),
        context.op_config,
        # A fixed batch-only token would reuse an earlier failed Databricks run.
        # The Dagster run ID keeps retries idempotent within this orchestration run,
        # while a later Dagster launch can start a fresh Databricks workload.
        f"{context.run_id}-bronze",
    )
    context.log_event(
        dg.AssetMaterialization(
            asset_key=s3_landing_files.key,
            metadata={
                "source_file": context.op_config["source_file_name"],
                "source_path": context.op_config["source_path"],
                "batch_id": context.op_config["batch_id"],
            },
        )
    )
    context.log_event(
        dg.AssetMaterialization(
            asset_key=bronze_transactions.key,
            metadata={
                "batch_id": context.op_config["batch_id"],
                "databricks_run_id": run_id,
            },
        )
    )
    context.log.info("Bronze completed with Databricks run ID %s", run_id)
    return run_id


@dg.op(retry_policy=RETRY_POLICY)
def run_silver(context: dg.OpExecutionContext, bronze_run_id: int) -> int:
    config = context.run_config["ops"]["run_bronze"]["config"]
    silver_params = {
        "catalog_name": config["catalog_name"],
        "source_file_name": config["source_file_name"],
        "batch_id": config["batch_id"],
    }
    run_id = run_databricks_job(
        required_env("DATABRICKS_SILVER_JOB_ID"),
        silver_params,
        f"{context.run_id}-silver",
    )
    context.log_event(
        dg.AssetMaterialization(
            asset_key=silver_transactions.key,
            metadata={"batch_id": config["batch_id"], "databricks_run_id": run_id},
        )
    )
    context.log.info("Silver completed with Databricks run ID %s", run_id)
    return run_id


@dg.op(retry_policy=RETRY_POLICY)
def load_snowflake_raw(context: dg.OpExecutionContext, silver_run_id: int) -> int:
    config = context.run_config["ops"]["run_bronze"]["config"]
    snowflake_load_params = {
        "catalog_name": config["catalog_name"],
        "source_file_name": config["source_file_name"],
        "batch_id": config["batch_id"],
    }
    run_id = run_databricks_job(
        required_env("DATABRICKS_SNOWFLAKE_LOAD_JOB_ID"),
        snowflake_load_params,
        f"{context.run_id}-snowflake-raw",
    )
    context.log_event(
        dg.AssetMaterialization(
            asset_key=snowflake_raw_transactions.key,
            metadata={"batch_id": config["batch_id"], "databricks_run_id": run_id},
        )
    )
    context.log.info("Snowflake RAW load completed with Databricks run ID %s", run_id)
    return run_id


@dg.op(retry_policy=RETRY_POLICY)
def validate_snowflake_raw(context: dg.OpExecutionContext, raw_load_run_id: int) -> int:
    batch_id = context.run_config["ops"]["run_bronze"]["config"]["batch_id"]
    row_count = get_snowflake_raw_batch_count(batch_id)
    if row_count == 0:
        raise RuntimeError(f"No rows found in Snowflake RAW for batch {batch_id}")
    context.log.info("Snowflake RAW validation passed: %s rows for batch %s", row_count, batch_id)
    return row_count


@dg.op(retry_policy=RETRY_POLICY)
def refresh_gold(context: dg.OpExecutionContext, validated_raw_row_count: int) -> str:
    execute_gold_refresh()
    batch_id = context.run_config["ops"]["run_bronze"]["config"]["batch_id"]
    context.log_event(
        dg.AssetMaterialization(
            asset_key=gold_analytics.key,
            metadata={"batch_id": batch_id, "validated_raw_row_count": validated_raw_row_count},
        )
    )
    context.log_event(
        dg.AssetMaterialization(
            asset_key=native_streamlit_dashboard.key,
            metadata={"batch_id": batch_id, "status": "Gold data refreshed"},
        )
    )
    return batch_id


@dg.op(retry_policy=RETRY_POLICY)
def archive_processed_file(context: dg.OpExecutionContext, gold_refresh_batch_id: str) -> None:
    """Copy a successfully processed landing file to archive/, then remove it from landing/."""
    source_path = context.run_config["ops"]["run_bronze"]["config"]["source_path"]
    parsed = urlparse(source_path)
    bucket = parsed.netloc
    source_key = parsed.path.lstrip("/")
    landing_prefix = os.getenv("S3_LANDING_PREFIX", "landing/")
    archive_prefix = os.getenv("S3_ARCHIVE_PREFIX", "archive/")

    if parsed.scheme != "s3" or not bucket or not source_key.startswith(landing_prefix):
        raise ValueError(f"Only S3 landing files can be archived. Received: {source_path}")

    relative_key = source_key[len(landing_prefix):]
    archive_key = f"{archive_prefix}{relative_key}"
    client = boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-south-1"))

    # Copy is completed before delete. If a retry occurs after a successful copy,
    # overwriting the same archive key is safe because landing object keys are immutable.
    client.copy_object(
        Bucket=bucket,
        Key=archive_key,
        CopySource={"Bucket": bucket, "Key": source_key},
    )
    client.delete_object(Bucket=bucket, Key=source_key)

    config = context.run_config["ops"]["run_bronze"]["config"]
    context.log_event(
        dg.AssetMaterialization(
            asset_key=s3_archived_files.key,
            metadata={
                "source_file": config["source_file_name"],
                "archived_s3_uri": f"s3://{bucket}/{archive_key}",
                "batch_id": config["batch_id"],
            },
        )
    )
    context.log.info("Archived batch %s to s3://%s/%s", gold_refresh_batch_id, bucket, archive_key)


@dg.job
def fraud_pipeline_job():
    bronze_run_id = run_bronze()
    silver_run_id = run_silver(bronze_run_id)
    raw_load_run_id = load_snowflake_raw(silver_run_id)
    validated_raw_row_count = validate_snowflake_raw(raw_load_run_id)
    gold_refresh_batch_id = refresh_gold(validated_raw_row_count)
    archive_processed_file(gold_refresh_batch_id)
