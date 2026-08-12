import os
from pathlib import Path

from dotenv import load_dotenv


# Loads the local ignored .env file when Dagster imports this package.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def required_env(name: str) -> str:
    """Return a required setting without ever printing the value."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
