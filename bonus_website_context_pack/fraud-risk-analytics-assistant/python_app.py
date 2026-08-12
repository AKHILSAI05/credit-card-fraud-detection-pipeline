"""No-dependency local demo server for Fraud Risk Analytics Assistant."""
from __future__ import annotations

import json
import re
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
APPROVED_OBJECTS = {"FRAUD_DB.ANALYTICS.FRAUD_DAILY_SUMMARY", "FRAUD_DB.ANALYTICS.AMOUNT_BUCKET_SUMMARY", "FRAUD_DB.ANALYTICS.RISK_TIME_DASHBOARD", "FRAUD_DB.ANALYTICS.ANALYST_REVIEW_QUEUE"}
BLOCKED_SQL = {"INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "ALTER", "DROP", "TRUNCATE", "COPY", "PUT", "GET", "CALL", "GRANT", "REVOKE", "USE", "EXECUTE", "IMMEDIATE", "RAW", "BRONZE", "SILVER", "INFORMATION_SCHEMA", "ACCOUNT_USAGE", "EXTERNAL"}

def sample_response(question: str) -> dict:
    q = question.lower()
    if "amount" in q and ("range" in q or "bucket" in q):
        return {"source":"Amount analysis", "title":"Amount range summary", "columns":["Amount range","Transaction count","Transaction amount","High review-priority count"], "data":[["$0–$50","112,481","$2.8M","1,218"],["$50–$200","74,221","$8.6M","2,033"],["$200–$500","22,314","$6.5M","1,509"],["$500+","5,982","$7.1M","1,874"]], "sql":"SELECT AMOUNT_RANGE, TRANSACTION_COUNT, TRANSACTION_AMOUNT, HIGH_REVIEW_PRIORITY_COUNT FROM FRAUD_DB.ANALYTICS.AMOUNT_BUCKET_SUMMARY ORDER BY HIGH_REVIEW_PRIORITY_COUNT DESC LIMIT 100"}
    if ("priority" in q or "early morning" in q or "recent" in q) and "time segment" not in q and "time window" not in q:
        return {"source":"Analyst review queue", "title":"Analyst review queue", "columns":["Transaction ID","Transaction time","Amount","Time segment","Review priority","Review score"], "data":[["TXN-2024-08192","2024-09-18 04:42","$1,248.90","Early Morning","High","98.4"],["TXN-2024-08183","2024-09-18 04:15","$982.00","Early Morning","High","91.7"],["TXN-2024-08177","2024-09-18 03:49","$768.40","Early Morning","High","88.2"]], "sql":"SELECT REVIEW_TRANSACTION_ID, TRANSACTION_TIME, TRANSACTION_AMOUNT, TIME_SEGMENT, REVIEW_PRIORITY, REVIEW_SCORE FROM FRAUD_DB.ANALYTICS.ANALYST_REVIEW_QUEUE WHERE REVIEW_PRIORITY = 'HIGH' ORDER BY TRANSACTION_TIME DESC LIMIT 100"}
    if "time segment" in q or "time window" in q:
        return {"source":"Risk and time analysis", "title":"Review priorities by time segment", "columns":["Time segment","Review priority","Transaction count","Transaction amount"], "data":[["Early Morning","High","1,246","$0.9M"],["Morning","Medium","2,872","$2.1M"],["Afternoon","Low","4,511","$3.2M"],["Evening","High","1,098","$1.0M"]], "sql":"SELECT TIME_SEGMENT, REVIEW_PRIORITY, TRANSACTION_COUNT, TRANSACTION_AMOUNT FROM FRAUD_DB.ANALYTICS.RISK_TIME_DASHBOARD ORDER BY TRANSACTION_COUNT DESC LIMIT 100"}
    return {"source":"Daily overview", "title":"Daily performance", "columns":["Transaction date","Transaction count","Total transaction amount","Historical fraud percentage"], "data":[["Sep 12, 2024","18,420","$1,478,500","0.18%"],["Sep 13, 2024","19,210","$1,539,200","0.21%"],["Sep 14, 2024","17,908","$1,422,800","0.16%"],["Sep 15, 2024","20,144","$1,637,100","0.19%"]], "sql":"SELECT TRANSACTION_DATE, TRANSACTION_COUNT, TRANSACTION_AMOUNT, HISTORICAL_FRAUD_PERCENTAGE FROM FRAUD_DB.ANALYTICS.FRAUD_DAILY_SUMMARY ORDER BY TRANSACTION_DATE LIMIT 1000"}

def validate_gold_sql(sql: str) -> tuple[bool, str]:
    normalized = sql.strip().upper()
    if not normalized.startswith(("SELECT ", "WITH ")): return False, "Only one read-only SELECT or CTE query is permitted."
    if ";" in normalized or "--" in normalized or "/*" in normalized: return False, "Multiple statements and SQL comments are not permitted."
    if "@" in normalized or "SYSTEM$" in normalized: return False, "Stages, system functions, and external access are not permitted."
    if any(token in normalized.split() for token in BLOCKED_SQL): return False, "This request is outside the approved Gold analytics policy."
    ctes = set(re.findall(r"(?:WITH|,)\s*([A-Z][A-Z0-9_]*)\s+AS\s*\(", normalized))
    sources = re.findall(r"\b(?:FROM|JOIN)\s+([A-Z0-9_\.]+)", normalized)
    if not sources: return False, "The query must use an approved FRAUD_DB.ANALYTICS Gold object."
    for source in sources:
        if source not in APPROVED_OBJECTS and source not in ctes:
            return False, "The query references a data source outside the approved Gold analytics policy."
    return True, ""

class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(ROOT), **kwargs)
    def do_GET(self):
        if urlparse(self.path).path == "/": self.path = "/dashboard.html"
        if urlparse(self.path).path == "/dashboard.html":
            html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
            body = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()
    def do_POST(self):
        if urlparse(self.path).path != "/api/query": return self.send_error(HTTPStatus.NOT_FOUND, "Not found")
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
            question = str(payload.get("question", "")).strip()
        except (ValueError, json.JSONDecodeError): return self._json(HTTPStatus.BAD_REQUEST, {"error":"Please provide a valid analytics question."})
        if not question: return self._json(HTTPStatus.BAD_REQUEST, {"error":"Please enter an analytics question."})
        result = sample_response(question)
        sql = result["sql"]
        ok, reason = validate_gold_sql(sql)
        if not ok: return self._json(HTTPStatus.BAD_REQUEST, {"error":reason})
        result.update({"status":"validated_sample", "message":"Sample data returned. A live Snowflake connection is not configured.", "rows":len(result["data"])})
        self._json(HTTPStatus.OK, result)
    def _json(self, status: HTTPStatus, data: dict):
        response = json.dumps(data).encode("utf-8"); self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(response))); self.end_headers(); self.wfile.write(response)

if __name__ == "__main__":
    print("Fraud Risk Analytics Assistant is running at http://127.0.0.1:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), AppHandler).serve_forever()
