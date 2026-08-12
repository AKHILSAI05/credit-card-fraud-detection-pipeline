import os
import hashlib
from datetime import datetime
from urllib.parse import urlparse

import boto3
import dagster as dg
from botocore.exceptions import ClientError

from .jobs import fraud_pipeline_job
from .resources import (
    databricks_content_hash_exists,
    databricks_processed_etag_hash,
    record_databricks_duplicate_content,
)


def calculate_s3_sha256(client, bucket: str, key: str) -> str:
    """Stream the S3 object and return a SHA-256 content fingerprint.

    The file is processed in chunks, so the entire object is never held in
    memory. The resulting hash detects identical content under different names.
    """
    digest = hashlib.sha256()
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    try:
        for chunk in iter(lambda: body.read(1024 * 1024), b""):
            digest.update(chunk)
    finally:
        body.close()
    return digest.hexdigest()


def route_duplicate_to_reject(client, bucket: str, source_key: str, destination_key: str) -> None:
    """Copy first, then remove landing source only after the reject copy succeeds."""
    client.copy_object(
        Bucket=bucket,
        Key=destination_key,
        CopySource={"Bucket": bucket, "Key": source_key},
    )
    client.delete_object(Bucket=bucket, Key=source_key)


def send_pipeline_failure_notification(
    context: dg.RunStatusSensorContext,
    source_file_name: str,
    batch_id: str,
    rejected_s3_uri: str | None,
) -> bool:
    """Publish an optional SNS alert for a final failed pipeline run.

    Notifications are deliberately opt-in: if SNS settings are absent, failure handling
    continues normally and the sensor records that no notification was sent.
    """
    topic_arn = os.getenv("SNS_FAILURE_TOPIC_ARN", "").strip()
    if not topic_arn:
        context.log.warning(
            "Pipeline failure notification not sent: configure SNS_FAILURE_TOPIC_ARN "
            "to enable alerts."
        )
        return False

    run = context.dagster_run
    subject = f"[Action required] Dagster pipeline failed: {run.job_name}"
    rejected_location = rejected_s3_uri or "Source file was not moved (no valid landing S3 path)."
    body = (
        "Dagster pipeline failure alert\n\n"
        f"Job: {run.job_name}\n"
        f"Run ID: {run.run_id}\n"
        f"Source file: {source_file_name}\n"
        f"Batch ID: {batch_id}\n"
        f"Rejected file location: {rejected_location}\n\n"
        "The run reached final FAILURE status after any configured retries. "
        "Review the Dagster run logs for the underlying error."
    )
    try:
        boto3.client("sns", region_name=os.getenv("AWS_REGION", "ap-south-1")).publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=body,
        )
    except ClientError as error:
        context.log.error("Pipeline failure SNS notification could not be sent: %s", error)
        return False

    context.log.info("Pipeline failure SNS notification published for run %s.", run.run_id)
    return True


@dg.sensor(
    job=fraud_pipeline_job,
    default_status=dg.DefaultSensorStatus.STOPPED,
    minimum_interval_seconds=30,
)
def landing_file_sensor(context: dg.SensorEvaluationContext):
    """Launch at most one run for the oldest unseen S3 key/ETag combination.

    S3_SENSOR_START_AFTER is optional ISO-8601 UTC time. It is used once when
    introducing the sensor to an existing landing folder: older objects are
    recorded in the cursor but are not launched.

    A second file remains in landing/ while a pipeline run is active. This
    prevents overlapping Bronze/Silver/Snowflake work for separate batches.
    """
    bucket = os.environ["S3_BUCKET"]
    prefix = os.getenv("S3_LANDING_PREFIX", "landing/")
    client = boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-south-1"))
    start_after_raw = os.getenv("S3_SENSOR_START_AFTER", "").strip()
    start_after = None
    if start_after_raw:
        start_after = datetime.fromisoformat(start_after_raw.replace("Z", "+00:00"))
    active_runs = context.instance.get_runs(
        filters=dg.RunsFilter(
            job_name=fraud_pipeline_job.name,
            statuses=[
                dg.DagsterRunStatus.QUEUED,
                dg.DagsterRunStatus.STARTING,
                dg.DagsterRunStatus.STARTED,
            ],
        ),
        limit=1,
    )
    if active_runs:
        return dg.SkipReason(
            "A fraud pipeline run is already active; waiting before starting the next landing file."
        )

    seen = set((context.cursor or "").split(",")) - {""}
    updated_seen = set(seen)
    candidates = []

    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            if key.endswith("/"):
                continue
            etag = item["ETag"].strip('"')
            run_key = f"{key}:{etag}"
            if run_key in seen:
                continue
            if start_after and item["LastModified"] <= start_after:
                # Old files are deliberately ignored when first enabling the sensor.
                updated_seen.add(run_key)
                continue
            candidates.append((item["LastModified"], key, etag, item["Size"], run_key))

    if not candidates:
        context.update_cursor(",".join(sorted(updated_seen)[-500:]))
        return dg.SkipReason("No new landing files found.")

    # Process the oldest unseen file first; leave all other files unseen for later runs.
    _, key, etag, file_size_bytes, run_key = min(candidates, key=lambda candidate: candidate[0])
    catalog_name = "workspace"
    source_file_name = key.rsplit("/", 1)[-1]
    source_path = f"s3://{bucket}/{key}"
    batch_id = f"s3_{etag[:12]}"
    updated_seen.add(run_key)
    context.update_cursor(",".join(sorted(updated_seen)[-500:]))

    # Fast path: an unchanged S3 upload has the same ETag.  Reuse the original
    # recorded SHA-256 instead of downloading a large file during a sensor tick.
    content_sha256 = databricks_processed_etag_hash(catalog_name, etag)
    is_duplicate = content_sha256 is not None

    # Fallback: ETags can differ for identical content in some upload methods,
    # so calculate a true content hash only when the fast ETag check is unknown.
    if not is_duplicate:
        content_sha256 = calculate_s3_sha256(client, bucket, key)
        is_duplicate = databricks_content_hash_exists(catalog_name, content_sha256)

    if is_duplicate:
        relative_key = key[len(prefix):]
        reject_prefix = os.getenv("S3_REJECT_DUPLICATES_PREFIX", "reject/duplicates/")
        reject_key = f"{reject_prefix}{relative_key}"
        routed_s3_uri = f"s3://{bucket}/{reject_key}"
        try:
            route_duplicate_to_reject(client, bucket, key, reject_key)
        except ClientError as error:
            # A previous sensor evaluation may have already copied and deleted
            # the same source object. Treat that race as a harmless skip.
            if error.response.get("Error", {}).get("Code") == "NoSuchKey":
                return dg.SkipReason(
                    f"Duplicate source {source_file_name} was already routed by another sensor tick."
                )
            raise
        record_databricks_duplicate_content(
            catalog_name=catalog_name,
            source_file_name=source_file_name,
            source_path=source_path,
            source_etag=etag,
            file_size_bytes=file_size_bytes,
            content_sha256=content_sha256,
            batch_id=batch_id,
            routed_s3_uri=routed_s3_uri,
        )
        context.log.info(
            "Duplicate content routed to reject/duplicates/ | "
            "source_file=%s | content_sha256=%s | rejected_s3_uri=%s",
            source_file_name,
            content_sha256,
            routed_s3_uri,
        )
        return dg.SkipReason(
            f"Duplicate content detected: {source_file_name} was routed to {routed_s3_uri}."
        )

    return dg.RunRequest(
        run_key=run_key,
        run_config={
            "ops": {
                "run_bronze": {
                    "config": {
                        "catalog_name": catalog_name,
                        "source_file_name": source_file_name,
                        "source_path": source_path,
                        "batch_id": batch_id,
                        "content_sha256": content_sha256,
                        "source_etag": etag,
                        "file_size_bytes": str(file_size_bytes),
                    }
                }
            }
        },
    )


@dg.run_status_sensor(
    run_status=dg.DagsterRunStatus.FAILURE,
    monitored_jobs=[fraud_pipeline_job],
    minimum_interval_seconds=15,
    default_status=dg.DefaultSensorStatus.STOPPED,
)
def pipeline_failure_reject_sensor(context: dg.RunStatusSensorContext):
    """Move a source file only after the final Dagster pipeline failure.

    The whole run must fail first, so normal retries are never interrupted.
    """
    config = (
        context.dagster_run.run_config.get("ops", {})
        .get("run_bronze", {})
        .get("config", {})
    )
    source_path = config.get("source_path", "")
    source_file_name = config.get("source_file_name", "unknown_file")
    batch_id = config.get("batch_id", "unknown_batch")

    parsed = urlparse(source_path)
    bucket = parsed.netloc
    source_key = parsed.path.lstrip("/")
    landing_prefix = os.getenv("S3_LANDING_PREFIX", "landing/")
    reject_prefix = os.getenv(
        "S3_REJECT_VALIDATION_FAILED_PREFIX", "reject/validation_failed/"
    )

    rejected_s3_uri = None
    if parsed.scheme == "s3" and bucket and source_key.startswith(landing_prefix):
        relative_key = source_key[len(landing_prefix):]
        reject_key = f"{reject_prefix}{relative_key}"
        client = boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-south-1"))
        try:
            route_duplicate_to_reject(client, bucket, source_key, reject_key)
        except ClientError as error:
            # A prior sensor tick or manual action may already have moved the file.
            if error.response.get("Error", {}).get("Code") != "NoSuchKey":
                raise
        rejected_s3_uri = f"s3://{bucket}/{reject_key}"
    else:
        context.log.warning("Failed pipeline did not contain a valid S3 landing source path; no file was moved.")

    notification_sent = send_pipeline_failure_notification(context, source_file_name, batch_id, rejected_s3_uri)
    context.log.info(
        "Pipeline failed after retries; routed source to validation_failed/ | "
        "source_file=%s | batch_id=%s | rejected_s3_uri=%s | notification_sent=%s",
        source_file_name,
        batch_id,
        rejected_s3_uri,
        notification_sent,
    )
    return dg.SkipReason(
        f"Pipeline failure handled: {source_file_name}; notification sent={notification_sent}."
    )
