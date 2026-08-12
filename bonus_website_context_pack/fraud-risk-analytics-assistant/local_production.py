"""Run the live Gemini + Snowflake application locally without persisting secrets."""
from __future__ import annotations

import getpass
import os
from pathlib import Path


def configure_secret(name: str, prompt: str) -> None:
    if not os.getenv(name):
        value = getpass.getpass(prompt).strip()
        if not value:
            raise SystemExit(f"{name} is required.")
        os.environ[name] = value


def configure_private_key() -> None:
    if os.getenv("SNOWFLAKE_PRIVATE_KEY"):
        return
    key_path = Path(input("Full path to the Snowflake private-key PEM file: ").strip().strip('"'))
    if not key_path.is_file():
        raise SystemExit("The private-key file was not found.")
    os.environ["SNOWFLAKE_PRIVATE_KEY"] = key_path.read_text(encoding="utf-8")


configure_secret("GEMINI_API_KEY", "Gemini API key (input is hidden): ")
configure_private_key()

defaults = {
    "GEMINI_MODEL": "gemini-3.5-flash-lite",
    "SNOWFLAKE_ACCOUNT": "disczwp-dv58220",
    "SNOWFLAKE_USER": "FRAUD_ANALYTICS_WEB_SVC",
    "SNOWFLAKE_WAREHOUSE": "FRAUD_WH",
    "SNOWFLAKE_ROLE": "FRAUD_ANALYTICS_WEB_READONLY",
    "SNOWFLAKE_DATABASE": "FRAUD_DB",
    "SNOWFLAKE_SCHEMA": "ANALYTICS",
    "QUERY_TIMEOUT_SECONDS": "30",
    "ALLOWED_ORIGINS": "http://127.0.0.1:8000,http://localhost:8000",
}
for setting, value in defaults.items():
    os.environ.setdefault(setting, value)

import uvicorn

print("Fraud Risk Analytics Assistant: http://127.0.0.1:8000")
uvicorn.run("production_app:app", host="127.0.0.1", port=8000, reload=False)
