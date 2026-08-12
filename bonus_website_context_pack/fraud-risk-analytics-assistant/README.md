# Fraud Risk Analytics Assistant

A dark, responsive analytics interface for asking plain-English questions about approved Snowflake Gold analytics data. The production Python API uses Gemini to propose SQL, validates it against a strict read-only allowlist, executes it with a restricted Snowflake service role, and returns table, chart, and CSV-ready results.

## Local architecture

1. The browser sends only the question and filters to `POST /api/query`.
2. The local Python server calls Gemini using the API key entered securely at startup.
3. The server permits one read-only `SELECT` or CTE against only the approved `FRAUD_DB.ANALYTICS` objects.
4. Snowflake is accessed with `FRAUD_ANALYTICS_WEB_SVC` and `FRAUD_ANALYTICS_WEB_READONLY`.
5. Results are capped at 1,000 rows; review-queue prompts request 100 rows.

No credential belongs in frontend code, this repository, logs, or CSV output.

## Run the live application locally

The working virtual environment is stored in the short Windows application-data path to avoid long-path installation errors. Install dependencies if needed:

```powershell
& "$env:LOCALAPPDATA\fraud-risk-venv\Scripts\python.exe" -m pip install -r ".\requirements.txt"
```

Download the Snowflake private-key PEM file to a secure folder outside the repository. Then start the local launcher:

```powershell
& "$env:LOCALAPPDATA\fraud-risk-venv\Scripts\python.exe" ".\local_production.py"
```

The launcher securely prompts for the Gemini API key and private-key file path, keeps their values only in the process environment, and opens the same live backend at `http://127.0.0.1:8000`. Never commit the PEM file or a real `.env` file.

Open `http://127.0.0.1:8000`. Keep the terminal open while using the website. The default model is `gemini-3.5-flash-lite`.

## Local safety tests

```powershell
& "$env:LOCALAPPDATA\fraud-risk-venv\Scripts\python.exe" -m unittest discover -s tests -v
```
