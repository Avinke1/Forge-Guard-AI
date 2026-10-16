# Run the ForgeGuard backend on your own computer

For Member 2 (AMD Task 5), Member 5 (tester) and the frontend team. Every command is given for
**macOS (Terminal)** and **Windows (PowerShell)**. Expected output is shown under each step.
The AMD key goes ONLY into `backend/.env` - never into chat, Git, screenshots or this file.

## 1. Get the code (branch `main`)

```
git clone https://github.com/Avinke1/Forge-Guard-AI.git
cd Forge-Guard-AI
```
(Or on GitHub: Code -> Download ZIP, unzip, open a terminal in the folder that contains `backend/`.)

## 2. Python 3.11 and the packages

macOS:
```
python3.11 --version
python3.11 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
```
Windows:
```
py -3.11 --version
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```
Expected: `Python 3.11.x`, then pip ends with `Successfully installed ... fastapi-0.143.2 ... uvicorn-0.54.0 ...`.
(No Python 3.11? Install it from python.org, or use `uv venv --python 3.11 .venv`.)

Optional check - tests never call AMD:
```
.venv/bin/python -m pytest              (macOS)
.venv\Scripts\python.exe -m pytest      (Windows)
```
Expected last line: `99 passed` (or more).

## 3. Settings file `backend/.env` (start with mock)

macOS: `cp backend/.env.example backend/.env` · Windows: `Copy-Item backend\.env.example backend\.env`

Keep `LLM_PROVIDER=mock` for now (no AI, no key needed). The other `LLM_*` lines are already correct for AMD.

## 4. Start the backend

macOS: `.venv/bin/python -m uvicorn backend.app.main:app --port 8000`
Windows: `.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000`

Expected: `Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)`. Leave this terminal open.

## 5. Check it (second terminal, same folder)

macOS: `.venv/bin/python scripts/try_api.py` · Windows: `.venv\Scripts\python.exe scripts\try_api.py`

Expected (real output, mock mode; the run_id differs every time):
```
ForgeGuard API check - http://localhost:8000
  PASS  GET /api/health: {"status": "ok", "version": "0.1.0"}
  PASS  GET /api/datasets: synthetic_fleet, metropt3
  PASS  POST /api/analyze/demo/synthetic_fleet: queue: HP-01 HIGH, FP-02 HIGH, HP-02 MEDIUM, DS-02 LOW, DS-01 OK, FP-01 OK
        run_id = 438df1923e5d
  PASS  GET /api/llm/status: provider=mock model=mock reachable=True error=None
  PASS  POST explain HP-01 (mock): HP-01: provider=mock model=mock latency_ms=0.0 grounding_rate=1.0 unsupported=0 cached=False
  PASS  POST explain FP-01 (no anomalies, no AI call): Rule-based summary (no AI): FP-01 - priority OK (score 0.00). ...
  PASS  unknown run -> 404 {error}: {"error": "Run not found. It may have expired - please run the analysis again."}
RESULT: PASS
```
Single calls by hand:

| What | macOS | Windows |
|---|---|---|
| health | `curl -s http://localhost:8000/api/health` | `curl.exe -s http://localhost:8000/api/health` |
| LLM status | `curl -s http://localhost:8000/api/llm/status` | `curl.exe -s http://localhost:8000/api/llm/status` |

Expected: `{"status":"ok","version":"0.1.0"}` and
`{"provider":"mock","model":"mock","hardware_label":"none - MOCK output, not AI","reachable":true,"last_latency_ms":0.0,"error":null}`.
Browser: http://localhost:8000/docs shows every endpoint and lets you try them.

## 6. Task 5 for Member 2 - real AMD, exactly 4 calls

The team shares **one key, 20 requests/min and a $1/day cap**. Run this ONCE.

1. Open `backend/.env` (macOS `nano backend/.env`, Windows `notepad backend\.env`) and set
   `LLM_PROVIDER=amd_token_factory` and `LLM_API_KEY=<the rc-... key>`. Save. Never show this file.
2. Stop uvicorn (CTRL+C) and start it again (step 4) - settings are read at start.
3. Check without spending anything: `scripts/try_api.py --task5` (with the python of step 5). Expected:
   `LLM status: provider=amd_token_factory model=DeepSeek-V4-Flash reachable=True error=None`
   and "Run again with --yes to start". (`llm/status` only lists models - no AI tokens.)
4. Start: `scripts/try_api.py --task5 --yes`. It runs the demo analyses and explains **HP-01, FP-02, HP-02**
   (synthetic_fleet) and **APU-01** (metropt3) - one at a time, 5 s apart, about 25 s each (12-36 s).
5. Paste the block `TASK 5 RESULT` to Member 1. Each line has: `provider`, `model` (exactly what AMD returned),
   `latency_ms`, `grounding_rate`, `unsupported` (count). Tested end to end with a fake AMD server:
   4 requests, 5+ s apart, key never printed.
6. Afterwards set `LLM_PROVIDER=mock` again, unless you go on with the saved demo reports.

**Scripts that save reports must use `ai_view()`** (it keeps only the notes linked to each anomaly - the API does
the same). Example for `scripts/save_demo_reports.py`:
```python
from backend.app import reports
from backend.app.pipeline import ai_view, run_demo

result = ai_view(run_demo("synthetic_fleet"))
case = next(c for c in result.cases if c.machine_id == "HP-01")
report = reports.explain_machine(result, "HP-01")        # one real AI call
reports.save_report("synthetic_fleet", case, report)     # only real AMD reports are accepted
```

## 7. For the frontend team (Members 3 + 6)

1. Do steps 1-5 with `LLM_PROVIDER=mock` (no key needed).
2. In the website use the base URL `http://localhost:8000`. Contract and examples: `docs/API.md`.
3. CORS allows `http://localhost:5173` by default. If your dev server uses another address, add it to
   `FRONTEND_ORIGINS` in `backend/.env` (comma-separated, e.g. `http://localhost:5173,http://localhost:3000`)
   and restart uvicorn.
4. Example:
```js
const API = "http://localhost:8000";
const run = await (await fetch(`${API}/api/analyze/demo/synthetic_fleet`, { method: "POST" })).json();
// run.cases is the inspection queue, already sorted (inspect run.cases[0] first)
const ctrl = new AbortController(); setTimeout(() => ctrl.abort(), 90000);   // real AI: about 25 s
const report = await (await fetch(`${API}/api/runs/${run.run_id}/explain/HP-01`,
                                  { method: "POST", signal: ctrl.signal })).json();
// report.explanation === null -> show report.error + report.fallback_summary
// badge ONLY from report.provenance.provider ("mock" -> "MOCK - not AI output")
```
5. A site opened from an `https://` address (for example an online preview) may be blocked by the browser
   from calling `http://localhost` - VERIFY in your browser. If it is blocked, run the frontend locally, or use
   the deployed HTTPS backend once it is up (STEP 5).

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| macOS: `CERTIFICATE_VERIFY_FAILED` / SSL error (AMD calls) | Finder -> Applications -> Python 3.11 -> double-click `Install Certificates.command`, then restart uvicorn |
| `address already in use` / port 8000 busy | macOS: `lsof -i :8000` then `kill <PID>`. Windows: `netstat -ano \| findstr :8000` then `taskkill /PID <PID> /F`. Or use `--port 8001` and `try_api.py --base http://localhost:8001` |
| `AMD key missing or invalid (HTTP 401)` | Check `LLM_API_KEY` in `backend/.env` (no spaces, no quotes, `rc-` + 48 characters), save, restart uvicorn |
| `AMD account still in review (HTTP 403)` | The AMD account is not verified yet - ask Member 2; nothing to fix in the code |
| `The team's daily AI limit ... is used up` | STOP all AI calls for today (shared $1/day). Use `LLM_PROVIDER=saved` (saved real reports) or `mock` |
| `Rate limit reached` (HTTP 429, 20/min) | Wait a minute; never run Task 5 in parallel with someone else |
| Changed `backend/.env`, nothing changed | Restart uvicorn - settings are read at start |
| Explain takes 25-40 s | Normal for the real AI. Mock answers at once |
| `Run not found` (404) | The backend restarted (runs live in memory) - run the analysis again |
