"""Production API boundary. Configure only with server-side secrets."""
from __future__ import annotations

import os
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import snowflake.connector
from snowflake.connector.errors import ProgrammingError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from python_app import validate_gold_sql

app = FastAPI(title="Fraud Risk Analytics Assistant", docs_url=None, redoc_url=None)
ROOT = Path(__file__).parent
GOLD_MODEL = """Approved objects and columns:
FRAUD_DB.ANALYTICS.FRAUD_DAILY_SUMMARY: TRANSACTION_DATE, TRANSACTION_COUNT, TRANSACTION_AMOUNT, AVERAGE_TRANSACTION_AMOUNT, MINIMUM_TRANSACTION_AMOUNT, MAXIMUM_TRANSACTION_AMOUNT, HISTORICAL_FRAUD_COUNT, HISTORICAL_LEGITIMATE_COUNT, HISTORICAL_FRAUD_PERCENTAGE, HIGH_REVIEW_PRIORITY_COUNT, MEDIUM_REVIEW_PRIORITY_COUNT, LOW_REVIEW_PRIORITY_COUNT, RAPID_REPEAT_COUNT.
FRAUD_DB.ANALYTICS.AMOUNT_BUCKET_SUMMARY: AMOUNT_RANGE, TRANSACTION_COUNT, TRANSACTION_AMOUNT, AVERAGE_TRANSACTION_AMOUNT, HISTORICAL_FRAUD_COUNT, HIGH_REVIEW_PRIORITY_COUNT, MEDIUM_REVIEW_PRIORITY_COUNT, LOW_REVIEW_PRIORITY_COUNT, RAPID_REPEAT_COUNT.
FRAUD_DB.ANALYTICS.RISK_TIME_DASHBOARD: TIME_SEGMENT, TIME_WINDOW, AMOUNT_BUCKET, REVIEW_PRIORITY, TRANSACTION_COUNT, TRANSACTION_AMOUNT, AVERAGE_TRANSACTION_AMOUNT, RAPID_REPEAT_COUNT, HISTORICAL_FRAUD_COUNT.
FRAUD_DB.ANALYTICS.ANALYST_REVIEW_QUEUE: REVIEW_TRANSACTION_ID, TRANSACTION_TIME, TRANSACTION_AMOUNT, AMOUNT_RANGE, TIME_SEGMENT, TIME_WINDOW, RAPID_REPEAT_INDICATOR, AMOUNT_OUTLIER_INDICATOR, AMOUNT_DEVIATION_SCORE, AMOUNT_PERCENTILE_RANK, REVIEW_SCORE, REVIEW_PRIORITY."""
origins = [item.strip() for item in os.getenv("ALLOWED_ORIGINS", "").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"])

class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1_000)
    filters: dict[str, str] = Field(default_factory=dict)

def require_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise HTTPException(503, "The secure analytics connection has not been configured.")
    return value

def enforce_result_limit(sql: str) -> str:
    sql = sql.strip().removesuffix(";").rstrip()
    match = re.search(r"\bLIMIT\s+(\d+)\b", sql, flags=re.I)
    if match and int(match.group(1)) > 1000:
        raise HTTPException(400, "Results are limited to 1,000 rows.")
    return sql if match else f"{sql.rstrip()} LIMIT 1000"

def validate_question(question: str) -> None:
    definitive_fraud_claim = re.search(
        r"\b(?:is|are|was|were|confirm(?:ed)?|prove|definitely)\b.{0,80}\b(?:fraud|fraudulent)\b",
        question,
        flags=re.I,
    )
    if definitive_fraud_claim:
        raise HTTPException(400, "This assistant cannot confirm that a transaction or person is fraudulent. Review Priority only organises operational review.")

def generate_sql(question: str, filters: dict[str, str]) -> str:
    """Generate candidate SQL through Gemini; validation remains mandatory."""
    api_key = require_setting("GEMINI_API_KEY")
    model_id = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    policy = f"""Return SQL only, with no markdown or explanation. Generate exactly one SELECT statement or read-only WITH CTE. Always use fully qualified object names. Use only the objects and columns listed below; never invent a column. ANALYST_REVIEW_QUEUE uses AMOUNT_RANGE and never AMOUNT_BUCKET. RISK_TIME_DASHBOARD uses AMOUNT_BUCKET and never AMOUNT_RANGE. The actual TIME_SEGMENT values are Morning, Afternoon, Evening, and Night. The actual TIME_WINDOW values are Business Hours and Off Hours. There is no Early Morning category; when a user says Early Morning, use TIME_SEGMENT = Morning. Never compare Morning, Afternoon, Evening, or Night against TIME_WINDOW. Compare category text case-insensitively with UPPER; for time values also normalize underscores with REPLACE(column, '_', ' '). Never use RAW, Bronze, Silver, information schema, account usage, stages, external functions, DDL, DML, procedures, comments, dynamic SQL, multiple statements, or a result limit over 1000. For ANALYST_REVIEW_QUEUE detail queries use LIMIT 100. Apply supplied filters only when their values are present and relevant. Review Priority is operational review order, not confirmed fraud. Historical Fraud is retrospective validation only, never a prediction.\n\n{GOLD_MODEL}"""
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(model_id, safe='-_.')}:generateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": policy}]},
        "contents": [{
            "role": "user",
            "parts": [{"text": f"Question: {question}\nFilters: {json.dumps(filters, separators=(',', ':'))}"}],
        }],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 700,
            "responseMimeType": "text/plain",
        },
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        sql = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise HTTPException(502, "The approved query-assistance service is unavailable.") from exc
    return re.sub(r"^```(?:sql)?\s*|\s*```$", "", sql, flags=re.I).strip()

def correct_known_column_aliases(sql: str) -> str:
    """Correct unambiguous concept aliases using the approved Gold model."""
    return re.sub(
        r"(FRAUD_DB\.ANALYTICS\.ANALYST_REVIEW_QUEUE\.)AMOUNT_BUCKET\b",
        r"\1AMOUNT_RANGE",
        sql,
        flags=re.I,
    )

def snowflake_connection():
    pem = require_setting("SNOWFLAKE_PRIVATE_KEY").replace("\\n", "\n").encode()
    private_key = load_pem_private_key(pem, password=None).private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return snowflake.connector.connect(account=require_setting("SNOWFLAKE_ACCOUNT"), user=require_setting("SNOWFLAKE_USER"), private_key=private_key, warehouse=require_setting("SNOWFLAKE_WAREHOUSE"), role=require_setting("SNOWFLAKE_ROLE"), database=require_setting("SNOWFLAKE_DATABASE"), schema=require_setting("SNOWFLAKE_SCHEMA"), login_timeout=15, network_timeout=30, client_session_keep_alive=False, session_parameters={"STATEMENT_TIMEOUT_IN_SECONDS": int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))})

def execute_sql(sql: str) -> tuple[list[str], list[list[Any]]]:
    connection = snowflake_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [description[0].replace("_", " ").title() for description in cursor.description]
            return columns, [list(row) for row in cursor.fetchmany(1000)]
    finally:
        connection.close()

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/")
def dashboard() -> HTMLResponse:
    html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
    return HTMLResponse(html)

@app.get("/dark.css")
def dashboard_css() -> FileResponse:
    return FileResponse(ROOT / "dark.css", media_type="text/css")

@app.get("/app.js")
def dashboard_js() -> FileResponse:
    return FileResponse(ROOT / "app.js", media_type="text/javascript")

@app.get("/api/freshness")
def data_freshness() -> dict[str, str | None]:
    """Return the latest date from the approved daily Gold summary."""
    sql = "SELECT MAX(TRANSACTION_DATE) AS LATEST_TRANSACTION_DATE FROM FRAUD_DB.ANALYTICS.FRAUD_DAILY_SUMMARY LIMIT 1"
    valid, reason = validate_gold_sql(sql)
    if not valid:
        raise HTTPException(500, reason)
    try:
        _, rows = execute_sql(sql)
    except ProgrammingError as exc:
        raise HTTPException(503, "Data freshness is temporarily unavailable.") from exc
    latest = rows[0][0] if rows and rows[0] else None
    return {"latest_transaction_date": str(latest) if latest is not None else None}

@app.post("/api/query")
async def query(request: QueryRequest) -> dict[str, Any]:
    validate_question(request.question)
    sql = correct_known_column_aliases(generate_sql(request.question, request.filters))
    sql = enforce_result_limit(sql)
    valid, reason = validate_gold_sql(sql)
    if not valid:
        raise HTTPException(400, reason)
    try:
        columns, rows = execute_sql(sql)
    except ProgrammingError as exc:
        raise HTTPException(400, "The generated query used a field that is not available in the approved analytics data. Please rephrase the question and try again.") from exc
    # Audit logging belongs here: timestamp, user/session ID, question, SQL hash,
    # execution result and row count. Never log credentials or private-key values.
    return {"status": "validated", "sql": sql, "columns": columns, "rows": rows, "row_count": len(rows)}
