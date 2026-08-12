import time
from typing import Any

import requests
import snowflake.connector

from .settings import required_env


def _databricks_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {required_env('DATABRICKS_TOKEN')}"}


def _databricks_sql_literal(value: str) -> str:
    """Quote an application value for a fixed internal Databricks SQL statement."""
    return value.replace("'", "''")


def execute_databricks_sql(statement: str) -> list[list[Any]]:
    """Execute a short Databricks SQL statement and return inline result rows.

    Dagster uses the configured SQL Warehouse only for audit-table checks and
    audit events. It never receives or writes a user's data files directly.
    """
    host = required_env("DATABRICKS_HOST").rstrip("/")
    response = requests.post(
        f"{host}/api/2.0/sql/statements",
        headers=_databricks_headers(),
        json={
            "warehouse_id": required_env("DATABRICKS_SQL_WAREHOUSE_ID"),
            "statement": statement,
            "wait_timeout": "30s",
            "disposition": "INLINE",
        },
        timeout=40,
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    statement_id = payload["statement_id"]

    while payload["status"]["state"] in {"PENDING", "RUNNING"}:
        time.sleep(2)
        response = requests.get(
            f"{host}/api/2.0/sql/statements/{statement_id}",
            headers=_databricks_headers(),
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

    if payload["status"]["state"] != "SUCCEEDED":
        message = payload["status"].get("error", {}).get("message", "Databricks SQL statement failed")
        raise RuntimeError(message)

    return payload.get("result", {}).get("data_array", [])


def databricks_content_hash_exists(catalog_name: str, content_sha256: str) -> bool:
    """Return True only when the exact file content completed Bronze successfully."""
    safe_catalog = catalog_name.replace("`", "")
    safe_hash = _databricks_sql_literal(content_sha256)
    rows = execute_databricks_sql(
        f"""
        SELECT COUNT(*) AS duplicate_count
        FROM {safe_catalog}.ops.processed_files
        WHERE content_sha256 = '{safe_hash}'
          AND status = 'SUCCESS'
          AND target_table = '{safe_catalog}.bronze.transactions_raw'
        """
    )
    return bool(rows and int(rows[0][0]) > 0)


def databricks_processed_etag_hash(catalog_name: str, source_etag: str) -> str | None:
    """Return the saved SHA-256 for a successfully processed S3 ETag, if known.

    This is a fast path for an object re-uploaded without any content change.
    It avoids downloading a large file in the Dagster sensor just to calculate
    its SHA-256 again. SHA-256 remains the fallback when the ETag is new.
    """
    safe_catalog = catalog_name.replace("`", "")
    safe_etag = _databricks_sql_literal(source_etag)
    rows = execute_databricks_sql(
        f"""
        SELECT content_sha256
        FROM {safe_catalog}.ops.processed_files
        WHERE source_etag = '{safe_etag}'
          AND status = 'SUCCESS'
          AND target_table = '{safe_catalog}.bronze.transactions_raw'
          AND content_sha256 IS NOT NULL
        ORDER BY completed_ts DESC
        LIMIT 1
        """
    )
    return str(rows[0][0]) if rows and rows[0] and rows[0][0] else None


def record_databricks_duplicate_content(
    *,
    catalog_name: str,
    source_file_name: str,
    source_path: str,
    source_etag: str,
    file_size_bytes: int,
    content_sha256: str,
    batch_id: str,
    routed_s3_uri: str,
) -> None:
    """Record a renamed-but-identical file that was routed to S3 reject/duplicates/."""
    safe_catalog = catalog_name.replace("`", "")
    values = {
        "source_file_name": source_file_name,
        "source_path": source_path,
        "source_etag": source_etag,
        "content_sha256": content_sha256,
        "batch_id": batch_id,
        "routed_s3_uri": routed_s3_uri,
    }
    safe = {key: _databricks_sql_literal(value) for key, value in values.items()}
    execute_databricks_sql(
        f"""
        INSERT INTO {safe_catalog}.ops.processed_files (
            source_file_name, source_s3_uri, source_etag, file_size_bytes,
            content_sha256, batch_id, pipeline_run_id, status,
            source_row_count, bronze_row_count, started_ts, completed_ts,
            error_message, rejection_reason, routed_s3_uri, target_table
        ) VALUES (
            '{safe['source_file_name']}', '{safe['source_path']}', '{safe['source_etag']}', {int(file_size_bytes)},
            '{safe['content_sha256']}', '{safe['batch_id']}', 'duplicate_{safe['batch_id']}', 'DUPLICATE_CONTENT',
            NULL, NULL, current_timestamp(), current_timestamp(),
            NULL, 'Identical file content was already processed successfully.', '{safe['routed_s3_uri']}',
            '{safe_catalog}.bronze.transactions_raw'
        )
        """
    )


def run_databricks_job(job_id: str, notebook_params: dict[str, str], idempotency_token: str) -> int:
    """Run a configured Databricks job and wait for successful completion."""
    host = required_env("DATABRICKS_HOST").rstrip("/")
    headers = {"Authorization": f"Bearer {required_env('DATABRICKS_TOKEN')}"}
    response = requests.post(
        f"{host}/api/2.2/jobs/run-now",
        headers=headers,
        json={
            "job_id": int(job_id),
            "notebook_params": notebook_params,
            "idempotency_token": idempotency_token[:64],
        },
        timeout=30,
    )
    response.raise_for_status()
    run_id = response.json()["run_id"]

    while True:
        response = requests.get(
            f"{host}/api/2.2/jobs/runs/get",
            headers=headers,
            params={"run_id": run_id},
            timeout=30,
        )
        response.raise_for_status()
        state: dict[str, Any] = response.json()["state"]
        if state["life_cycle_state"] in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
            if state.get("result_state") != "SUCCESS":
                raise RuntimeError(state.get("state_message", "Databricks job failed"))
            return run_id
        time.sleep(15)


def execute_gold_refresh() -> None:
    """Call the Snowflake stored procedure after a successful RAW load."""
    connection = snowflake.connector.connect(
        account=required_env("SNOWFLAKE_ACCOUNT"),
        user=required_env("SNOWFLAKE_USER"),
        password=required_env("SNOWFLAKE_PASSWORD"),
        role=required_env("SNOWFLAKE_ROLE"),
        warehouse=required_env("SNOWFLAKE_WAREHOUSE"),
        database=required_env("SNOWFLAKE_DATABASE"),
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("CALL ANALYTICS.REFRESH_FRAUD_GOLD()")
    finally:
        connection.close()


def get_snowflake_raw_batch_count(batch_id: str) -> int:
    """Confirm that the loaded batch exists in Snowflake RAW before Gold refresh."""
    connection = snowflake.connector.connect(
        account=required_env("SNOWFLAKE_ACCOUNT"),
        user=required_env("SNOWFLAKE_USER"),
        password=required_env("SNOWFLAKE_PASSWORD"),
        role=required_env("SNOWFLAKE_ROLE"),
        warehouse=required_env("SNOWFLAKE_WAREHOUSE"),
        database=required_env("SNOWFLAKE_DATABASE"),
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM RAW.TRANSACTIONS WHERE BATCH_ID = %s", (batch_id,))
            return int(cursor.fetchone()[0])
    finally:
        connection.close()
