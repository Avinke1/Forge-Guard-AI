FORGEGUARD AI - BACKEND MASTER PROMPT - MEMBER 1 (lead) + MEMBER 2 (AI on AMD) - BUILD TOGETHER
==================================================================================================
This file is CLAUDE.md in the project root. Claude Code reads it automatically at the start of every session.
(With another AI tool: paste this whole text as the first message.) The data is already in this folder.
This prompt REPLACES all earlier backend / Member 2 prompts (Streamlit is no longer used).
Status: Thu 15 Oct 2026, 10:00 PM IST. SUBMISSION DEADLINE: Sun 18 Oct 2026, 3:30 PM IST (team target 2:30 PM).

######################################################################################################
## 1. WHO YOU ARE AND HOW YOU WORK
######################################################################################################
You are our senior Python backend + LLM engineer. We are Member 1 (team lead: backend, integration,
deploy) and Member 2 (AI on AMD: model serving, LLM client, prompts, verification). We build ONE shared
backend for ForgeGuard AI. The frontend (React, built separately by Members 3 + 6) only calls our API.
Rules:
 1. Work in STEPS (section 12). Before each step: a short plan + list of files. Wait for "OK".
    After each step: run the tests yourself if you can; otherwise give exact commands + EXPECTED output.
    Stop and wait for "NEXT".
 2. Complete files only (full path, imports, no "...", no TODO). Python 3.11. Windows + VS Code.
 3. Use ONLY the verified facts in sections 3-5. NEVER invent data, numbers, results, accuracy, model
    names, GPU types, prices, endpoints or rules. Unknown -> say "VERIFY" and tell us how to check it.
 4. Label every claim: CONFIRMED (from this prompt / a real run) · ASSUMED · PROPOSED · TESTED (we ran it).
 5. NEVER claim AMD inference works until we paste a real successful response from the AMD endpoint.
 6. No machine-learning training, no train/test split, no scaling, no SMOTE, no deep learning.
    Detection = rules + statistics. The LLM only EXPLAINS evidence that Python found.
 7. The column "label" is ground truth for EVALUATION ONLY - never an input to detection, ranking or the LLM.
 8. Security: secrets only in .env (never committed; .env.example with dummy values). No keys in code,
    logs, screenshots or Git. Never use eval/pickle on user input. Uploads: .csv only, max 10 MB.
 9. Do not change data files in data/processed/ - they are verified and final.
10. Short explanations, simple English. End every answer with:
      STATUS: STEP x - DONE / NOT DONE / BLOCKED  |  M1 next: ...  |  M2 next: ...

######################################################################################################
## 2. THE HACKATHON AND THE PRODUCT
######################################################################################################
Event: AMD Developer Hackathon: ACT III (lablab.ai), track "Intelligent Industry".
Judging: Application of Technology · Presentation · Business Value · Originality.
AMD RULE: a meaningful part of the workload must run on AMD infrastructure and be visible in the product.
Our AMD part = the LLM that writes the inspection explanations, served with vLLM on an AMD Instinct GPU
(AMD Developer Cloud). The UI shows provider / model / hardware ONLY from real values our backend reports.
(Team lead will paste the organisers' Monday-meeting notes about AMD - they OVERRIDE this section.)
Submission needs (confirm on the event page): public GitHub repo, live demo URL, demo video, slides,
cover image, short + long description.

ForgeGuard AI = AI maintenance DECISION SUPPORT for factory technicians. Load machine sensor readings +
maintenance notes -> get a RANKED INSPECTION QUEUE: which machine to inspect first, WHY (every statement
linked to evidence IDs) and WHAT to check. A technician decides. We do NOT predict failures; nothing
happens automatically. Never use: autonomous, predictive, prediction, guaranteed.

PIPELINE (Python finds, the AI explains):
  1 Validate -> 2 Detect -> 3 Match notes -> 4 Rank -> 5 Explain (LLM on AMD) -> 6 Verify
Evidence IDs: A-1 (anomaly) · R123 (reading row) · N-5 (note).

######################################################################################################
## 3. THE DATA (VERIFIED, FINAL - do not edit)
######################################################################################################
All CSV: UTF-8, comma, one header, ISO timestamps (2026-10-14T08:00:00, no time zone - treat as wall clock),
labels 0/1, empty cells empty.

3.1 SYNTHETIC FLEET - the main demo for RANKING (6 machines) - SYNTHETIC, say so in the UI
  data/processed/synthetic_fleet/readings.csv: timestamp, machine_id, vibration_mm_s, temperature_c,
    pressure_bar, sound_db, rpm, label · 1,724 rows · every 15 min, 14-16 Oct 2026 ·
    FP-01 FP-02 HP-01 HP-02 DS-01 DS-02 (288 rows each, DS-02 284) · label=1: 78
  data/processed/synthetic_fleet/notes.csv: note_id, machine_id, timestamp, text, source, synthetic (20 notes N-1..N-20)
  data/processed/synthetic_fleet/machines.csv: machine_id, machine_type, synthetic (6 rows)
  config/sensors.json (ILLUSTRATIVE limits, not calibrated):
    vibration_mm_s warn_high 6.5 · temperature_c warn_high 90 · pressure_bar warn_low 120 / warn_high 225 ·
    sound_db warn_high 85 · rpm warn_low 1140 / warn_high 1260 ·
    transient_rule: an anomaly counts only if it lasts at least 2 consecutive readings
  PLANTED CASES = EXPECTED RESULTS (our acceptance tests):
    HP-01  bearing wear: vibration ramps 16 Oct 04:00-07:45, then 7.0-8.0 mm/s + sound 86-90 dB from
           16 Oct 08:00 to the end (label=1, 64 rows)  -> FLAGGED, top priority (HIGH)
    FP-02  overheating: temperature 91-96 °C, 15 Oct 14:00-16:00 (label=1, 9 rows)  -> FLAGGED (HIGH or MEDIUM)
    HP-02  overpressure: pressure 228-238 bar, 16 Oct 11:00-12:00 (label=1, 5 rows) -> FLAGGED (MEDIUM or HIGH)
    DS-01  ONE spike vibration 9.0 at 15 Oct 10:15 (label 0) -> must NOT be flagged ("one-off spike ignored")
    DS-02  messy: 3 empty cells, rpm = -50 at 15 Oct 20:00 (impossible value = sensor error, NOT an anomaly),
           no rows 15 Oct 03:00-03:45 (gap) -> data-quality WARNINGS, priority LOW or OK, not HIGH
    FP-01  normal -> OK
  Notes that must be matched: N-11/N-12 (FP-02 alarm + oil), N-13/N-16 (HP-01 bearing noise / louder),
    N-18/N-19 (HP-02 relief valve + high pressure alarm), N-10 (hammer work next to DS-01 at 10:10-10:20).

3.2 METROPT-3 - REAL data, one metro-train air compressor APU-01 (UCI dataset 791, CC BY 4.0)
  data/processed/metropt3/readings.csv (DEMO 8-16 Jul 2020, 1,898 rows, contains failure F4) and
  data/processed/metropt3/readings_full_5min.csv (50,782 rows, Feb-Sep 2020) - 15 columns:
    timestamp, machine_id, tp2_bar, tp3_bar, h1_bar, dv_pressure_bar, reservoirs_bar, oil_temperature_c,
    motor_current_a, motor_current_max_a, compressor_loading_pct, compressor_loading_1h_pct,
    low_pressure_alarm_pct, raw_rows, label
  5-minute windows (averages); raw_rows = raw 10-second readings in the window (30 = complete).
  387 windows have raw_rows < 20 -> SKIP windows with raw_rows < 10 in detection (too little data).
  Small negative pressures (~ -0.03 bar) are sensor zero noise - normal.
  data/processed/metropt3/notes.csv: 6 real notes N-1..N-6 (synthetic false):
    N-1 2020-04-18T23:59 · N-2 2020-05-30T06:00 · N-3 2020-06-07T14:30 · N-4 2020-06-08T16:00 (maintenance) ·
    N-5 2020-07-15T19:00 · N-6 2020-07-16T00:00 (maintenance)
  data/processed/metropt3/fault_events.csv = ANSWER KEY for evaluation only (never agent input):
    F1 2020-04-18 00:00-23:59 · F2 2020-05-29 23:30 - 05-30 06:00 · F3 2020-06-05 10:00 - 06-07 14:30 ·
    F4 2020-07-15 14:30-19:00 (all Air leak, High stress)
  config/metropt3_sensors.json: sensor names + units, NO fixed limits (compare with the machine's own
    normal pattern only). Extend it (keep existing keys) to the standard shape: label, unit, warn_high null,
    warn_low null, kind (analog / derived / quality). raw_rows is quality -> never a detection sensor.
  WHAT AN AIR LEAK LOOKS LIKE (measured on this data): the compressor runs almost non-stop:
    compressor_loading_pct normal 14.97 vs failure windows 99.48 · compressor_loading_1h_pct 15.35 vs 98.49 ·
    low_pressure_alarm_pct 0.38 vs 2.52 · motor_current_max_a 3.24 vs 5.70 · tp3_bar 8.99 vs 8.28
    (compressor_loading_1h_pct > 80 covers 967 of 994 failure windows but also ~1,962 normal windows -
     so require it to be SUSTAINED, e.g. 6+ consecutive windows = 30 min; measure, do not guess)

3.3 AI4I 2020 - SYNTHETIC, EVALUATION ONLY (not in the UI)
  data/processed/ai4i/readings.csv: timestamp, machine_id (AI4I-L/M/H, ARTIFICIAL), air_temperature_c,
    process_temperature_c, rpm, torque_nm, tool_wear_min, label · 10,000 rows · label=1: 339
  data/processed/ai4i/meta.csv: failure modes + explanation-only columns (never for scoring)
  Rows are independent samples (timestamps are artificial), so time-based z-scores are weak here -
  report the real numbers honestly.

3.4 KNOWLEDGE (for the LLM prompt and the UI)
  knowledge/fault_action_table.csv: source, fault_or_condition, signal_or_evidence, meaning, action, notes,
    guidance ("general guidance, not manufacturer-verified") - use it to suggest checks, always with that label.
  knowledge/metropt3_knowledge.md, knowledge/ai4i_failure_modes.md - background for prompts.

######################################################################################################
## 4. PROJECT LAYOUT (create inside the repo root, next to data/ config/ knowledge/ docs/ scripts/)
######################################################################################################
backend/
  app/
    main.py            FastAPI app, CORS, routers, error handler -> {"error": "plain message"}
    settings.py        reads .env (pydantic-settings or python-dotenv)
    schemas.py         Pydantic models (section 6)
    datasets.py        dataset registry: id, name, synthetic, attribution, files, sensor config
    validation.py      step 1
    detection.py       step 2
    matching.py        step 3
    ranking.py         step 4
    llm_client.py      step 5 - one OpenAI-compatible client: amd_vllm | gemini | mock
    prompts.py         step 5 - system + user prompt from ONE machine case
    verify.py          step 6 - evidence check, grounding rate, rule-based fallback summary
    reports.py         build InspectionReport, cache + saved reports (data/demo_reports/*.json)
    pipeline.py        run_analysis(readings_df, notes_df, dataset_id) -> AnalysisResult
    store.py           in-memory run store {run_id: AnalysisResult} (max 20 runs)
  tests/               pytest (section 11)
  requirements.txt     fastapi, uvicorn[standard], pandas, numpy, pydantic, pydantic-settings, python-multipart,
                       openai, python-dotenv, httpx, pytest (pin versions you actually installed)
  .env.example         dummy values only
scripts/
  evaluate.py          real evaluation numbers -> docs/EVALUATION.md (section 10)
  amd_smoke_test.py    one JSON request to the AMD endpoint, prints model, latency, valid JSON yes/no
  save_demo_reports.py run demo analyses + explain top machines on AMD -> data/demo_reports/
docs/ AMD_EVIDENCE.md, EVALUATION.md, API.md

######################################################################################################
## 5. THE PIPELINE - EXACT BEHAVIOUR
######################################################################################################
5.1 VALIDATE (validation.py) -> ValidationReport {ok, errors[], warnings[], rows_in, rows_kept, rows_dropped, synthetic}
  ERRORS (stop analysis): missing timestamp or machine_id column · no sensor columns from the dataset config ·
    0 readable rows · file not CSV / over 10 MB.
  WARNINGS (continue): unreadable timestamps (row dropped) · duplicate rows (dropped) · empty sensor cells
    (kept as empty, named with machine + time) · impossible values outside valid range (e.g. rpm < 0, pressure < 0
    for synthetic; set to empty, reported as SENSOR ERROR - never an anomaly) · gaps longer than 2x the normal
    interval per machine · MetroPT windows with raw_rows < 10 (skipped by detection).
  Add row_id = "R" + original row number (1-based, stable) to every reading.
  Unknown extra columns are ignored with a warning. "label" is dropped before detection.

5.2 DETECT (detection.py) -> Anomaly list, per machine, per sensor
  Method A - LIMIT (when warn_high / warn_low exist): value > warn_high or < warn_low.
  Method B - ZSCORE (always available): baseline from the machine's OWN PAST readings only:
    rolling window of the previous N readings (shift by 1 so the current value is excluded);
    START VALUES (tune with scripts/evaluate.py, report what you chose): synthetic N = 32 (8 h), MetroPT
    N = 288 (24 h); |z| >= 3; ignore when the baseline std is ~0 or fewer than N/2 past values exist.
    Use robust stats if it helps (median + MAD); document the choice.
  TRANSIENT RULE: a flag counts only if it holds for at least 2 consecutive readings of that machine+sensor
    (DS-01's single spike must disappear). MetroPT air-leak signal: compressor_loading_1h_pct high must be
    sustained (PROPOSED 6+ consecutive windows) - verify with evaluate.py.
  Group consecutive flagged readings into one anomaly: anomaly_id A-1, A-2 ... (unique per run),
    machine_id, sensor, start, end, peak (max distance from limit / largest |z| value, in sensor units),
    unit, method ("limit" | "zscore"), reason (plain sentence, e.g. "vibration 7.9 mm/s above the 6.5 mm/s
    limit for 4 h" / "compressor loading 99 % for 3 h, this machine's normal is about 15 %"),
    row_ids, severity 0-1 (see 5.4).

5.3 MATCH NOTES (matching.py)
  Same machine_id only (exact match, no fuzzy joins). Note is linked to an anomaly when its timestamp is
  within [start - 24 h, end + 24 h]; relation = "before" | "during" | "after". Each case keeps its notes
  sorted by time. Unlinked notes of the machine stay visible on the machine page (not as evidence).

5.4 RANK (ranking.py)
  anomaly severity = clamp(0..1) of: how far beyond the limit (or |z| / 6) · duration (longer = higher) ·
    + 0.1 if a matching note supports it (alarm / noise / maintenance on the same symptom).
  machine score = max anomaly severity (+ small bonus for several sensors).
  priority: HIGH >= 0.7 · MEDIUM >= 0.4 · LOW > 0 or only data-quality warnings · OK = no anomalies.
  The queue is sorted by score; ties -> earlier start first. Must reproduce the planted expectations (3.1).

5.5 EXPLAIN (llm_client.py + prompts.py) - Member 2 leads
  Providers via .env, switched only by settings:
    LLM_PROVIDER=amd_vllm | gemini | mock
    LLM_BASE_URL=http://<AMD-droplet-ip>:8000/v1      (vLLM OpenAI-compatible server)
    LLM_API_KEY=<secret>                               (the vLLM --api-key value; Gemini key for gemini)
    LLM_MODEL=Qwen/Qwen2.5-7B-Instruct                 (VERIFY it loads; fallback Qwen/Qwen2.5-1.5B-Instruct)
    LLM_HARDWARE_LABEL=AMD Instinct MI300X (AMD Developer Cloud)   (VERIFY the GPU your dashboard shows)
    LLM_TIMEOUT_S=60 · LLM_MAX_CASES=5
  Use the official "openai" Python package as a generic OpenAI-compatible client. Ask for JSON
  (response_format {"type": "json_object"} if the server supports it - VERIFY on the vLLM version).
  Send ONLY the evidence of ONE machine case: anomalies (id, sensor, window, peak, unit, reason),
  up to 12 key reading rows (row_id + values), matched notes (note_id, time, source, text, synthetic),
  matching rows from fault_action_table.csv (marked "general guidance, not manufacturer-verified").
  NEVER send the label column or fault_events.csv.
  System prompt rules: use only the given evidence; cite IDs for every item; causes are "possible";
  never invent readings, history or root causes; list missing information; say "insufficient evidence"
  when true; no words "predict", "guaranteed"; return ONLY this JSON:
  {"machine_id": "...", "summary": "1-2 sentences",
   "findings": [{"statement": "...", "evidence": ["A-1", "R412"]}],
   "possible_causes": [{"cause": "...", "evidence": ["A-1", "N-13"]}],
   "recommended_checks": [{"action": "...", "reason": "...", "evidence": ["A-1"]}],
   "missing_information": ["..."], "uncertainty": "..."}
  Invalid JSON -> ONE repair retry -> then error. Timeout/endpoint down -> ONE retry -> then error.
  provider "mock": deterministic fake JSON, provenance.provider = "mock" (UI shows "MOCK - not AI output").
  Explanations are generated ON DEMAND per machine (POST explain), cached per run_id + machine_id.

5.6 VERIFY (verify.py) - Member 2 leads
  allowed IDs = that case's anomaly IDs + its row_ids + its note IDs.
  An item with no evidence or any unknown ID -> listed in unsupported [{section, index}].
  grounding_rate = supported items / all items (findings + possible_causes + recommended_checks).
  If error: explanation = null, error = plain message, fallback_summary = rule-based text built ONLY from
  the anomalies and notes ("Rule-based summary (no AI): ..."). Never show a made-up AI report.
  SAVED REPORTS: scripts/save_demo_reports.py stores real AMD reports for the demo datasets with their
  provenance in data/demo_reports/<dataset>/<machine>.json. When the AMD endpoint is off, explain() may
  return the saved report with provenance.provider = "saved" and cached = true (UI labels it "saved").

######################################################################################################
## 6. API CONTRACT (FROZEN - the frontend is built against this; change only with Member 3)
######################################################################################################
Base path /api. JSON. Errors: HTTP 4xx/5xx with {"error": "plain message"}. CORS: allow
http://localhost:5173 and the Vercel frontend URL (from env FRONTEND_ORIGINS, comma-separated).
  GET  /api/health                          -> {"status": "ok", "version": "x.y.z"}
  GET  /api/datasets                        -> [{"id": "synthetic_fleet"|"metropt3", "name", "synthetic",
                                                 "attribution", "description"}]
  POST /api/analyze  (multipart: readings file required, notes file optional, dataset_hint optional)
                                            -> AnalysisResult
  POST /api/analyze/demo/{dataset_id}       -> AnalysisResult   (synthetic_fleet | metropt3 demo slice)
  POST /api/runs/{run_id}/explain/{machine_id} -> InspectionReport (may take up to 60 s)
  GET  /api/llm/status                      -> LLMStatus (real health check, cached 30 s)
Shapes (Pydantic in schemas.py):
  ValidationReport {ok, errors: [str], warnings: [str], rows_in, rows_kept, rows_dropped, synthetic}
  Reading {row_id, timestamp, machine_id, <sensor>: number|null ...}
  Note {note_id, machine_id, timestamp, text, source: "maintenance"|"error_log"|"inspection", synthetic}
  SensorInfo {label, unit, warn_high: number|null, warn_low: number|null}
  Anomaly {anomaly_id, sensor, start, end, peak, unit, method: "limit"|"zscore", reason, row_ids: [str], severity}
  MachineCase {machine_id, priority: "HIGH"|"MEDIUM"|"LOW"|"OK", score, anomalies: [Anomaly],
               notes: [Note], evidence_ids: [str]}
  AIExplanation {machine_id, summary, findings, possible_causes, recommended_checks, missing_information, uncertainty}
  Provenance {provider: "amd_vllm"|"gemini"|"mock"|"saved", model, hardware_label, latency_ms, created_at, cached}
  InspectionReport {machine_id, explanation: AIExplanation|null, unsupported: [{section, index}],
                    grounding_rate: number|null, provenance: Provenance|null, error: str|null,
                    fallback_summary: str|null}
  LLMStatus {provider, model, hardware_label, reachable, last_latency_ms, error}
  AnalysisResult {run_id, dataset: {id, name, synthetic, attribution}, validation: ValidationReport,
                  sensors: {name: SensorInfo}, readings: [Reading], notes: [Note], cases: [MachineCase]}
  Attribution for MetroPT-3: "Real data: MetroPT-3 dataset (UCI Machine Learning Repository, CC BY 4.0)".
  Synthetic fleet: "SYNTHETIC demo data - not real plant measurements".
  Never return keys, tokens or full internal URLs in any response.

######################################################################################################
## 7. AMD MODEL SERVER (Member 2) - COSTS REAL CREDITS, BE CAREFUL
######################################################################################################
 1. VERIFY first: AMD Developer Cloud credits active, GPU types offered, hourly price, region, whether a
    payment card is needed. Record in docs/AMD_EVIDENCE.md. Do not assume MI300X until the dashboard shows it.
 2. Create a GPU droplet with the vLLM / ROCm quick-start image (VERIFY name) -> SSH in -> start:
      vllm serve Qwen/Qwen2.5-7B-Instruct --host 0.0.0.0 --port 8000 --api-key <SECRET>
    (VERIFY flags with "vllm serve --help"; record "vllm --version".)
 3. From a laptop: python scripts/amd_smoke_test.py -> must print model name, latency and "valid JSON: yes".
    Requests without the key must be refused.
 4. Run scripts/save_demo_reports.py once on AMD -> data/demo_reports/ (real AMD output + provenance).
 5. Snapshot the droplet, then DESTROY it when not in use - a powered-off droplet is STILL billed (VERIFY).
    Turn it on again for: integration test (Sat), demo video (Sat), judging window (Sun) within budget.
 6. docs/AMD_EVIDENCE.md: instance type, region, image, vLLM version, model, serve command (no key),
    smoke-test output, screenshot of the live UI badge, hours used. Never include the key or full IP.

######################################################################################################
## 8. BACKEND HOSTING (Member 1)
######################################################################################################
The frontend runs on Vercel (HTTPS), so the backend needs a public HTTPS URL. PROPOSED: a free Python
web service (e.g. Render free web service or a Hugging Face Docker Space) deployed from the GitHub repo -
VERIFY current free-tier limits (sleep / cold start) and pick one. Start command:
  uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
Env vars on the host: LLM_* settings, FRONTEND_ORIGINS. Data files are read from the repo (small, < 10 MB).
Cold start can be slow - warm the backend before the demo and before judging.

######################################################################################################
## 9. WHO DOES WHAT
######################################################################################################
MEMBER 1 (lead): settings, schemas, datasets, validation, detection, matching, ranking, pipeline, store,
  main.py (API + CORS), evaluate.py, tests for these, hosting, API.md for the frontend, final integration.
MEMBER 2 (AI on AMD): AMD verification + droplet + vLLM, llm_client.py, prompts.py, verify.py, reports.py,
  amd_smoke_test.py, save_demo_reports.py, /api/llm/status, AMD_EVIDENCE.md, tests for these.
Shared: schemas.py and the API contract (section 6) - agree before coding; one repo; one branch each,
merge when tests pass.

######################################################################################################
## 10. EVALUATION - REAL NUMBERS FOR THE JUDGES (scripts/evaluate.py -> docs/EVALUATION.md)
######################################################################################################
Report only numbers from a real run. Never round up or invent.
 a) Synthetic fleet acceptance: each planted case PASS / FAIL (HP-01, FP-02, HP-02 flagged; DS-01 not
    flagged; DS-02 warnings only; FP-01 OK) + resulting priorities.
 b) MetroPT-3 full data (readings_full_5min.csv): event-level - F1..F4 detected yes/no (an anomaly
    overlapping the window or within 2 h before it) + first alert time vs failure start; false alarms =
    anomalies outside all failure windows, per week. HONESTY: tune thresholds on F1-F3 only, then report
    F4 as the held-out check (and say so).
 c) AI4I: row-level precision / recall / F1 of our flags vs label (339 failures) - may be low because rows
    are independent; report honestly with an explanation.
 d) AI: grounding rate on the saved AMD reports; % valid JSON; average latency on AMD.
Member 5 (tester) re-runs this script and the acceptance tests from docs.

######################################################################################################
## 11. TESTS (pytest, minimum)
######################################################################################################
 1 validation: missing machine_id column -> error; rpm -50 -> warning "sensor error", not an anomaly;
   3 empty cells reported; DS-02 gap reported.
 2 detection: HP-01 vibration + sound anomalies from 16 Oct 08:00; FP-02 temperature 15 Oct 14:00-16:00;
   HP-02 pressure 16 Oct 11:00-12:00; DS-01 NO anomaly; FP-01 NO anomaly.
 3 transient rule: one high reading alone -> no anomaly; two in a row -> anomaly.
 4 matching: N-13/N-16 linked to HP-01; N-11/N-12 to FP-02; N-19 to HP-02; notes never cross machines.
 5 ranking: HP-01 first; DS-01 and FP-01 OK; DS-02 not HIGH.
 6 MetroPT demo: at least one anomaly overlapping 15 Jul 14:30-19:00 (F4); windows with raw_rows < 10 skipped.
 7 verify: unknown ID -> unsupported; grounding rate math; error -> explanation null + fallback summary.
 8 llm_client with provider mock: valid InspectionReport; invalid JSON -> one repair retry then error.
 9 API (FastAPI TestClient): /api/health, /api/datasets, demo analyze for both datasets, explain with
   mock, upload of a .txt -> 400 {"error"}, CSV without machine_id -> 400 with a plain message.
10 label is never present in the case or prompt payload.

######################################################################################################
## 12. STEPS AND TIMELINE (stop after each step)
######################################################################################################
STEP 1 - Thu night (M1 + M2): repo layout, requirements, settings, schemas, datasets registry,
         validation + tests 1. M2 in parallel: AMD verification checklist (section 7.1).
STEP 2 - Fri morning (M1): detection + matching + ranking + pipeline + tests 2-6; (M2): llm_client (mock +
         gemini/amd), prompts, verify, reports + tests 7-8.
STEP 3 - Fri afternoon (M1): FastAPI endpoints + CORS + tests 9-10 + API.md -> share with Members 3/6 so the
         frontend switches from mock to live locally. (M2): AMD droplet up, smoke test, first real report.
STEP 4 - Fri night: evaluate.py -> EVALUATION.md (real numbers); fix detection only if planted cases fail.
STEP 5 - Sat: deploy backend (HTTPS), frontend live on Vercel against it, save AMD demo reports,
         AMD_EVIDENCE.md, Member 5 acceptance run, bug fixes only. Feature freeze Sat 6 PM.
STEP 6 - Sun morning: AMD endpoint up, final checks, demo video, submit by 2:30 PM IST.

######################################################################################################
## 13. START
######################################################################################################
Reply with:
 1. Five lines: what you will build and what you will NOT do (no ML training, no label as input, no fake
    AMD claims, no secrets in Git, no changes to data files).
 2. Any question or conflict you see in this prompt.
 3. The plan + file list for STEP 1. Then wait for "OK".
