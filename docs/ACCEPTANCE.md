# Acceptance run (Member 5)

Run every step from the repo root `ForgeGuard-Backend/` on Windows. Write PASS/FAIL next to each line and send
the filled list + any error text to Member 1. Do not edit code or data files.

## 1. Setup

```
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r backend/requirements.txt
```

## 2. Automated tests

```
.venv/Scripts/python.exe -m pytest
```
Expected: last line `96 passed` (or more), nothing failed.

## 3. Evaluation numbers

```
.venv/Scripts/python.exe scripts/evaluate.py
```
Expected first line: `Synthetic planted cases: 6/6 PASS`, and `MetroPT F4 (held-out): YES`.
Then `git diff docs/EVALUATION.md`: only the "Generated ... on <date>" line may change.

## 4. Local API (mock AI)

```
.venv/Scripts/python.exe -m uvicorn backend.app.main:app --port 8000
```
In a second terminal (or the browser at http://localhost:8000/docs):

| Check | Expected |
|---|---|
| GET `/api/health` | `{"status":"ok","version":"0.1.0"}` |
| GET `/api/datasets` | 2 datasets: `synthetic_fleet` (synthetic true), `metropt3` (synthetic false) |
| POST `/api/analyze/demo/synthetic_fleet` | queue: HP-01 HIGH, FP-02 HIGH, HP-02 MEDIUM, DS-02 LOW, DS-01 OK, FP-01 OK |
| POST `/api/runs/<run_id>/explain/HP-01` | `provenance.provider` = `mock`, summary starts "MOCK - not AI output", `grounding_rate` 1.0 |
| POST `/api/runs/<run_id>/explain/FP-01` | `explanation` null, `fallback_summary` starts "Rule-based summary (no AI)" |
| POST `/api/analyze/demo/metropt3` | APU-01 HIGH, anomalies on 15 Jul 2020 between 16:55 and 18:45 |
| POST `/api/analyze` with a .txt file | HTTP 400 `{"error": "Only .csv files are accepted ..."}` |
| POST `/api/analyze` with a CSV without `machine_id` | HTTP 400, message mentions machine_id |
| GET `/api/llm/status` | `provider` mock, `reachable` true |

## 5. Deployed backend (after STEP 5 deploy)

Same table as 4 against `https://<service>.onrender.com` (first call may take about 1 minute - it wakes up).
Plus: the Vercel frontend loads both demos, shows the SYNTHETIC banner + attribution, and every AI box shows the
provider badge from the backend (MOCK / saved / AMD model name) - never a hard-coded "AMD".

## 6. Words check (UI + docs)

None of these words may appear in the UI or slides: autonomous, predictive, prediction, guaranteed.
