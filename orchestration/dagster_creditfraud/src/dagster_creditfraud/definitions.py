import dagster as dg

from .assets import all_assets
from .jobs import fraud_pipeline_job
from .sensors import landing_file_sensor, pipeline_failure_reject_sensor

defs = dg.Definitions(
    assets=all_assets,
    jobs=[fraud_pipeline_job],
    sensors=[landing_file_sensor, pipeline_failure_reject_sensor],
)
