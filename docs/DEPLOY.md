# Deploy the backend (Render, free web service)

Why Render: Hugging Face Docker Spaces now need a paid plan to create (checked 16 Oct 2026 in the HF docs).
Render free web service (checked 16 Oct 2026 in the Render docs): HTTPS included, 0.1 CPU / 512 MB RAM,
**sleeps after 15 min without traffic, wakes in about 1 minute**, 750 free hours per month per workspace.

## One-time setup (Member 1)

1. Push this repo to GitHub (public repo is required for the submission anyway).
2. Render dashboard -> **New** -> **Blueprint** -> pick the GitHub repo. Render reads `render.yaml`:
   - build: `pip install -r backend/requirements.txt`
   - start: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
   - health check: `/api/health`
   - Python 3.11 from `.python-version`
3. Render asks for the secret values (entered in the dashboard only, never in Git):

| Variable | Value |
|---|---|
| `FRONTEND_ORIGINS` | `http://localhost:5173,https://<our-app>.vercel.app` (exact Vercel production URL, no trailing slash) |
| `FRONTEND_ORIGIN_REGEX` | optional, for Vercel preview URLs, e.g. `https://<project>-[a-z0-9-]+\.vercel\.app`; leave empty if unsure |
| `LLM_API_KEY` | the team's AMD Token Factory key (`rc-...`) - typed into the Render dashboard only |

Already set by `render.yaml` (change in the dashboard if needed): `LLM_PROVIDER=mock`,
`LLM_BASE_URL=https://developer.amd.com.cn/radeon/api/v1`, `LLM_MODEL=DeepSeek-V4-Flash`,
`LLM_FALLBACK_MODEL=MiMo-V2.6-Flash`, `LLM_HARDWARE_LABEL`, `LLM_TIMEOUT_S=60`, `LLM_MAX_CASES=5`.

`LLM_PROVIDER` starts as `mock`. Switch it to `amd_token_factory` in the Render dashboard (Environment) when
the real AI should run; Render redeploys automatically. The team shares a **$1/day** AMD cap and 20 requests/min:
one explanation costs about 25 s and one or two requests, so keep live AI for the demo and judging.

4. After the deploy: open `https://<service>.onrender.com/api/health` -> `{"status":"ok","version":"0.1.0"}`.
5. Give the URL to Members 3 + 6: Vercel env var for the API base URL = `https://<service>.onrender.com`.

## Before the demo video and before judging

- Wake the backend: open `/api/health` and wait for the JSON (up to about 1 minute after sleep).
- Then `/api/llm/status` -> `reachable: true` and the real model name (when the AMD provider is on).
- Runs are kept in memory only: after a sleep/restart an old `run_id` gives 404 "Run not found" -
  the frontend just runs the analysis again.

## Rollback / safe mode

- `LLM_PROVIDER=saved` -> no live AI at all: the saved real AMD reports (`data/demo_reports/`, made by
  `scripts/save_demo_reports.py`) are shown with the badge "saved"; other machines get the rule-based summary.
- `LLM_PROVIDER=mock` -> the app works without AMD; every AI box shows "MOCK - not AI output".
- With `amd_token_factory`, a saved report is also served automatically when AMD is rate-limited, the daily cap
  is used up or the service is down (only if the machine's anomalies still match the saved report).
