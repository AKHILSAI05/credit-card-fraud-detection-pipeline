# Snowflake RAW Load Notebook

`snowflake_incremental_load.ipynb` runs in Databricks after the Silver transformation. It selects the current Silver batch and writes it to the Snowflake `FRAUD_DB.RAW` layer.

Required widgets:

- `catalog_name`
- `source_file_name`
- `batch_id`

The notebook reads its Snowflake password through the Databricks secret scope `fraud-snowflake`; no password is stored in this repository. Before running it, create the secret scope/key in Databricks and update connection settings only through secure runtime configuration.

