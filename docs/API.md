# ForgeGuard AI - Backend API (for Members 3 + 6)

Contract: CLAUDE.md section 6 (FROZEN). Pydantic source of truth: `backend/app/schemas.py`.
All examples below are REAL responses from the backend (`LLM_PROVIDER=mock`, final AI files).

## Run it locally

```
cd ForgeGuard-Backend
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r backend/requirements.txt
.venv/Scripts/python.exe -m uvicorn backend.app.main:app --port 8000
```

Base URL: `http://localhost:8000` (deployed HTTPS URL comes in STEP 5). Interactive docs: `/docs`.
CORS allows `http://localhost:5173` and the origins in `FRONTEND_ORIGINS` (comma-separated).

## Endpoints

| Method | Path | Returns | Notes |
|---|---|---|---|
| GET | `/api/health` | `{"status": "ok", "version": "0.1.0"}` | |
| GET | `/api/datasets` | `DatasetInfo[]` | `synthetic_fleet`, `metropt3` |
| POST | `/api/analyze` | `AnalysisResult` | multipart: `readings` (.csv, required), `notes` (.csv, optional), `dataset_hint` (optional) |
| POST | `/api/analyze/demo/{dataset_id}` | `AnalysisResult` | `synthetic_fleet` or `metropt3`; about 0.2 s |
| POST | `/api/runs/{run_id}/explain/{machine_id}` | `InspectionReport` | on demand, one machine; real AI about 25 s (12-36 s) - client timeout >= 90 s |
| GET | `/api/llm/status` | `LLMStatus` | real health check (model list, no AI tokens used), cached 30 s |

## Errors

Every error is HTTP 4xx/5xx with exactly one key:

```json
{"error": "Only .csv files are accepted (got 'r.txt')."}
```

| Status | When |
|---|---|
| 400 | not .csv, empty, over 10 MB, not readable CSV, missing `timestamp`/`machine_id`, no sensor columns, missing `readings` field, unknown `dataset_hint` |
| 404 | unknown demo dataset, unknown `run_id` (runs live in memory: newest 20, lost on restart - just run the analysis again), machine not in the run |
| 500 | `{"error": "Internal server error. Please try again."}` |

Show `error` text to the user as-is; it is written in plain English.

## AnalysisResult

```json
{
  "run_id": "a7c6a36dd19a",
  "dataset": {"id": "synthetic_fleet", "name": "Synthetic factory fleet (6 machines)", "synthetic": true,
              "attribution": "SYNTHETIC demo data - not real plant measurements"},
  "validation": {"ok": true, "errors": [], "warnings": ["Empty cell: DS-02 temperature_c at 2026-10-14T09:00:00 (R1477) - kept as empty.", "..."],
                 "rows_in": 1724, "rows_kept": 1724, "rows_dropped": 0, "synthetic": true},
  "sensors": {"vibration_mm_s": {"label": "Vibration", "unit": "mm/s", "warn_high": 6.5, "warn_low": null, "kind": "analog"}, "...": {}},
  "readings": [{"row_id": "R1153", "timestamp": "2026-10-14T00:00:00", "machine_id": "DS-01",
                "vibration_mm_s": 1.87, "temperature_c": 59.1, "pressure_bar": 148.2, "sound_db": 68.4, "rpm": 1220.0}],
  "notes": [{"note_id": "N-11", "machine_id": "FP-02", "timestamp": "2026-10-15T14:20:00",
             "text": "FP-02 high temperature alarm acknowledged by operator.", "source": "error_log", "synthetic": true}],
  "cases": ["MachineCase, already sorted: first = inspect first"]
}
```

- `readings`: one object per row; sensor keys = keys of `sensors`; empty value = `null`.
- Timestamps: ISO 8601 wall clock, no time zone (`2026-10-15T14:00:00`). Do not convert time zones.
- `sensors[...].kind == "quality"` (MetroPT `raw_rows`) is a data-quality count - do not chart it as a sensor.
- `warn_high` / `warn_low` are `null` for MetroPT-3 (no fixed limits - each sensor is compared with the machine's own past).

### MachineCase (the inspection queue)

```json
{
  "machine_id": "FP-02", "priority": "HIGH", "score": 0.7,
  "anomalies": [{
    "anomaly_id": "A-2", "machine_id": "FP-02", "sensor": "temperature_c",
    "start": "2026-10-15T14:00:00", "end": "2026-10-15T16:00:00", "peak": 96.0, "unit": "°C",
    "method": "limit", "reason": "Temperature 96 °C above the 90 °C limit for 2 h (9 readings).",
    "row_ids": ["R441", "R442", "R443", "..."], "severity": 0.7,
    "linked_notes": [{"note_id": "N-11", "relation": "during"}, {"note_id": "N-12", "relation": "after"}]
  }],
  "notes": ["all notes of this machine, sorted by time (linked AND unlinked)"],
  "evidence_ids": ["A-2", "R441", "...", "N-11"],
  "context": [{"kind": "gap", "message": "Data gap: DS-02 has no readings between ...", "start": "2026-10-15T02:45:00",
               "end": "2026-10-15T04:00:00", "sensor": null, "row_ids": ["R1548", "R1549"], "note_ids": ["N-9"]}]
}
```

- `priority`: `HIGH` (score >= 0.7) · `MEDIUM` (>= 0.4) · `LOW` (> 0, or data-quality warnings only) · `OK` (nothing found).
- `cases` is already in queue order - do not re-sort.
- A note is evidence only if its ID is in `evidence_ids`; other notes are background.
- `method`: `limit` (above/below the configured limit) or `zscore` (unusual compared with this machine's own past).

### Additions to the frozen contract (additive, all have defaults)

| Field | Meaning |
|---|---|
| `SensorInfo.kind` | `analog` / `derived` / `quality` |
| `Anomaly.machine_id` | machine of the anomaly |
| `Anomaly.linked_notes` | `[{note_id, relation: before/during/after}]` |
| `MachineCase.context` | data-quality warnings and ignored one-off spikes, with nearby notes. Show on the machine page as context, NOT as evidence. `kind`: `empty_cell`, `unreadable_value`, `sensor_error`, `gap`, `low_raw_rows`, `transient_ignored` |
| `Provenance.provider` | `amd_token_factory` (real AI on AMD), `mock`, `saved` (stored real AMD report), `gemini` (optional backup, never AMD) |

## InspectionReport (explain)

**Timing:** a real AMD explanation takes about **25 s (seen 12-36 s)**. Show a loading state and use a client
timeout of **at least 90 s**. Explain one machine at a time: the team shares a $1/day AMD limit.

Success (real mock output, lists shortened; with the real AI only the text and `provenance` differ):

```json
{
  "machine_id": "HP-01",
  "explanation": {
    "machine_id": "HP-01",
    "summary": "MOCK - not AI output. HP-01: 3 unusual reading pattern(s); strongest: Vibration 8 mm/s above the 6.5 mm/s limit for 15 h 45 min (64 readings)..",
    "findings": [{"statement": "MOCK: Vibration - Vibration 8 mm/s above the 6.5 mm/s limit for 15 h 45 min (64 readings).", "evidence": ["A-5", "R801"]}],
    "possible_causes": [{"cause": "MOCK: possibly related to note N-13 (before A-5).", "evidence": ["A-5", "N-13"]}],
    "recommended_checks": [{"action": "MOCK: Inspect bearings mounting alignment and rotating parts; confirm with repeat readings",
                            "reason": "(general guidance, not manufacturer-verified)", "evidence": ["A-5"]}],
    "missing_information": ["MOCK output - set LLM_PROVIDER=amd_token_factory for a real AI explanation."],
    "uncertainty": "MOCK output - not written by an AI model."
  },
  "unsupported": [],
  "grounding_rate": 1.0,
  "provenance": {"provider": "mock", "model": "mock", "hardware_label": "none - MOCK output, not AI",
                 "latency_ms": 0.0, "created_at": "2026-10-16T13:46:54Z", "cached": false},
  "error": null,
  "fallback_summary": null
}
```

With the real AI, `provenance` looks like `{"provider": "amd_token_factory", "model": "self-dploy/DeepSeek-V4-Flash",
"hardware_label": "AMD GPUs - AMD Token Factory (Radeon Cloud)", "latency_ms": 26309, ...}` - show `model` exactly as returned.

No AI explanation (no anomalies, AI unavailable, invalid AI output, daily limit used up, ...):

```json
{
  "machine_id": "FP-01", "explanation": null, "unsupported": [], "grounding_rate": null, "provenance": null,
  "error": "No unusual readings for this machine, so no AI explanation was requested.",
  "fallback_summary": "Rule-based summary (no AI): FP-01 - priority OK (score 0.00). No unusual readings were found."
}
```

`GET /api/llm/status` (mock): `{"provider": "mock", "model": "mock", "hardware_label": "none - MOCK output, not AI", "reachable": true, "last_latency_ms": 0.0, "error": null}`

## UI rules (from CLAUDE.md - please follow)

- `explanation == null` -> show `error` + `fallback_summary`. Never show an AI box then.
- Badge from `provenance` ONLY (never hard-code):
  - `mock` -> **"MOCK - not AI output"**
  - `saved` -> **"saved"** (a stored real AMD report, shown when the AMD endpoint is off or the daily limit is used up)
  - `amd_token_factory` -> show `model` + `hardware_label` exactly as returned
  - `gemini` -> show `model` + `hardware_label` (it says "not AMD") - never an AMD badge
  - `cached: true` -> optional "cached" tag
- `unsupported` = `[{section, index}]` -> mark that item (e.g. `findings[1]`) as "not supported by evidence".
- `grounding_rate` = supported items / all items; show as a percentage.
- Evidence chips: `A-n` -> anomaly, `R123` -> reading row, `N-n` -> note. Click to highlight.
- `dataset.synthetic == true` -> show a "SYNTHETIC data" banner; always show `dataset.attribution`.
- Checks based on the guidance table say "(general guidance, not manufacturer-verified)" - keep that text.
- Never use the words: autonomous, predictive, prediction, guaranteed. A technician decides.
- `/api/llm/status` -> header indicator (`reachable`, `provider`, `model`, `hardware_label`).
