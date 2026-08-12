# Databricks Pipeline Notebooks

These notebooks are the transformation steps invoked by the Dagster pipeline.

| Notebook | Pipeline stage | Required widgets |
|---|---|---|
| `bronze_incremental_load.sql.ipynb` | S3 landing CSV to `workspace.bronze.transactions_raw` | `catalog_name`, `source_file_name`, `source_path`, `batch_id`, `content_sha256`, `source_etag`, `file_size_bytes` |
| `silver_incremental_transform.sql.ipynb` | Bronze batch validation and risk-feature transformation to `workspace.silver.transactions_silver_incremental` | `catalog_name`, `source_file_name`, `batch_id` |

Both notebooks record batch/audit status in `workspace.ops` and use the `batch_id` passed by Dagster so reruns can be handled safely.

Import these notebooks into Databricks and configure the corresponding Bronze and Silver Jobs with the same widget parameter names used by `orchestration/dagster_creditfraud`.

