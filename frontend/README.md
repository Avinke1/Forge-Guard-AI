# ForgeGuard AI - Frontend

Maintenance decision support for factory technicians: a ranked inspection queue that shows **which machine to inspect first, why (with links to the exact readings and notes), and what to check**. A qualified technician makes the decision.

This folder is the **user interface only**. All analysis and all AI explanations are done by the ForgeGuard backend (FastAPI). The AI explanation is written by an open model served with AMD Token Factory. The frontend never analyses data, never calls an AI service and holds no API keys.

## Run locally
```bash
npm install
npm run dev        # http://localhost:3000
```

## Mock mode vs live mode
Copy `.env.example` to `.env`:
```
VITE_USE_MOCK=true                       # mock data, yellow banner on every page
VITE_API_BASE_URL=http://localhost:8000  # backend URL (used when VITE_USE_MOCK=false)
```
Switch to live: set `VITE_USE_MOCK=false` and point `VITE_API_BASE_URL` to the deployed backend. Nothing else changes - every backend call is in `src/api.ts`. The backend contract is in `API_CONTRACT.md`.

## Deploy on Vercel
- Root Directory: `frontend` - Framework: Vite - Build: `npm run build` - Output: `dist`
- Environment variables: `VITE_USE_MOCK`, `VITE_API_BASE_URL` (public values only, never secrets)
- `vercel.json` rewrites all routes to `index.html`, so `/queue` etc. work on refresh.

## Pages
`/` overview + one-click demo - `/upload` CSV upload and demo datasets - `/queue` ranked inspection queue - `/machines/:id` charts, unusual readings, notes, AI explanation with evidence chips - `/history` saved runs - `/status` AI service status (only values the backend reports).

## Data
- Synthetic fleet (SYNTHETIC): 6 machines, 14-16 Oct 2026, made by the team.
- MetroPT-3 (Real data: UCI, CC BY 4.0): one metro train air compressor (APU-01).
