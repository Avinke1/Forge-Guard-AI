# ForgeGuard AI — AMD Token Factory Evidence

**Hackathon:** AMD Developer Hackathon, ACT III  
**Owner:** Member 2 — AMD integration, explanation verification, and evidence  
**Evidence status:** TASK 6 v3 APPROVED by Member 1; Task 7 documentation DRAFT pending screenshot attachments and final review  
**Updated:** 17 October 2026 (IST)

> **Evidence integrity:** The final demo artifacts are the four unedited, AMD-generated **Task 6 v3** JSON reports in `data/demo_reports/` and `ForgeGuard_Task6_v3.zip`. Earlier Task 6 versions are superseded. Preserve the real AI text, including accepted minor wording imperfections; do not regenerate or hand-edit those outputs.

## 1. AMD integration and hosting

| Component | Verified configuration or observation |
|---|---|
| Inference provider | AMD Token Factory (`amd_token_factory`), verified in live backend report provenance |
| API base URL | `https://developer.amd.com.cn/radeon/api/v1` |
| Generation endpoint | `/chat/completions` |
| Model listing | `/models` |
| Usage | `/usage` — returned HTTP 200 |
| Primary model | `DeepSeek-V4-Flash`; inference responses identify `self-dploy/DeepSeek-V4-Flash` |
| Fallback model | `MiMo-V2.6-Flash`, successfully tested during model comparison |
| Report hardware label | `AMD GPUs - AMD TokenFactory (Radeon Cloud)` (reported provenance label; underlying accelerator placement has **not** been independently verified) |

The LLM is used to **explain anomalies detected by rule-based/analytical Python components**, not to invent readings, determine ground-truth fault labels, or issue autonomous maintenance commands. The pipeline sends only a machine's applicable evidence and links recommendations to evidence IDs.

**Secret handling:** The AMD token remains in the ignored local `backend/.env` file; never include it in this document, screenshots, a ZIP, Git, or chat. The production environment must likewise store credentials in private environment variables rather than source code. At the latest documented checkpoint, `LLM_PROVIDER=mock` was restored after v3 generation.

## 2. Task 2 — AMD API connectivity

The team successfully queried the model catalog, generated chat completions using both `DeepSeek-V4-Flash` and `MiMo-V2.6-Flash`, and retrieved usage information. This established API connectivity and the availability of the tested models. Sanitized request/response screenshots are still to be attached; authorization headers and keys must be hidden.

## 3. Task 3 — AMD live smoke test (PASS)

The existing `scripts/amd_smoke_test.py` was executed against AMD Token Factory.

| Metric | Observed value |
|---|---|
| Response model | `self-dploy/DeepSeek-V4-Flash` |
| Latency | 26,309 ms |
| Parseable structured JSON | Yes |
| Evidence-ID grounding | 1.0 (100%) |
| Unsupported evidence IDs | 0 |
| Fallback used | No |

This validates the tested response shape and cited-ID validity. It does not independently establish the correctness of every numerical or causal sentence.

## 4. Task 4 — model comparison (PASS)

| Model | Trial 1 (ms) | Trial 2 (ms) | Trial 3 (ms) | Mean (ms) |
|---|---:|---:|---:|---:|
| DeepSeek-V4-Flash | 28,243 | 12,261 | 36,147 | 25,550 |
| MiMo-V2.6-Flash | 24,590 | 22,877 | 28,232 | 25,233 |

All six trials generated valid JSON with grounding 1.0, no unsupported evidence IDs, and no fallback. The team chose **DeepSeek-V4-Flash** as primary and **MiMo-V2.6-Flash** as fallback. These three-trial means do not establish a statistically reliable performance difference.

## 5. Task 5 — live end-to-end backend verification (PASS)

Four actual, uncached AMD explanations were generated through the ForgeGuard API, each returning HTTP 200.

| Dataset | Machine | Reported model | Inference latency (ms) | Grounding | Unsupported IDs | Cached |
|---|---|---|---:|---:|---:|---|
| synthetic_fleet | HP-01 | `self-dploy/DeepSeek-V4-Flash` | 23,357 | 100% | 0 | No |
| synthetic_fleet | FP-02 | `self-dploy/DeepSeek-V4-Flash` | 26,750 | 100% | 0 | No |
| synthetic_fleet | HP-02 | `self-dploy/DeepSeek-V4-Flash` | 21,340 | 100% | 0 | No |
| metropt3 | APU-01 | `self-dploy/DeepSeek-V4-Flash` | 25,668 | 100% | 0 | No |

**Average observed inference latency:** approximately **24,279 ms**. In all four outputs, provenance identified `amd_token_factory`.

**Backend and environment checks:** Python 3.11 environment was set up on macOS; the local backend ran via Uvicorn; automated tests passed; after Task 5, `LLM_PROVIDER=mock` and `/api/llm/status` confirmed mock mode. The Git status check was clean and did not display `backend/.env`.

## 6. Task 6 v3 — saved AMD demo reports (APPROVED)

Member 1 merged the first set of detector/prompt changes into `main` (fix commit `7146d5f`, merge commit `3b1b59c`). Member 2 then installed Member 1's **Fix 2** updates to `backend/app/prompts.py` and `backend/app/verify.py` locally and confirmed `pytest -q` exited successfully (`0`). The Fix 2 files were not authorized for Member 2's PR; their incorporation into `main` is Member 1's responsibility.

After removing previous JSON reports, the script `scripts/save_demo_reports.py` was run **once** in AMD mode and saved these **v3** outputs without manual edits:

| Dataset | Machine | Latency (ms) | Findings | Recommended checks | Uncertainty | Grounding | Unsupported IDs | Saved |
|---|---|---:|---:|---:|---|---:|---:|---|
| synthetic_fleet | HP-01 | 41,541 | 3 | 3 | Present | 100% | 0 | Yes |
| synthetic_fleet | FP-02 | 21,822 | 2 | 2 | Present | 100% | 0 | Yes |
| synthetic_fleet | HP-02 | 26,778 | 1 | 3 | Present | 100% | 0 | Yes |
| metropt3 | APU-01 | 30,586 | 3 | 3 | Present | 100% | 0 | Yes |

All four original report provenances identify provider `amd_token_factory` and returned model `self-dploy/DeepSeek-V4-Flash`. Their JSON paths are:

- `data/demo_reports/synthetic_fleet/HP-01.json`
- `data/demo_reports/synthetic_fleet/FP-02.json`
- `data/demo_reports/synthetic_fleet/HP-02.json`
- `data/demo_reports/metropt3/APU-01.json`

**Report package:** `ForgeGuard_Task6_v3.zip` (contains four JSON reports). **Member 1 explicitly APPROVED Task 6 v3** and instructed that the reports must **not be regenerated or hand-edited**. The recommended demo machines are **HP-01** and **APU-01**.

### Task 6 v3 content audit

| Machine | Numerical evidence checked against Member 1's reference | Only anomaly sensors described as unusual? | Checks / uncertainty | Wording caveat | Review outcome |
|---|---|---|---|---|---|
| HP-01 | Vibration 8.0 mm/s; sound 90 dB; sustained window 16 Oct 08:00–23:45 | Yes | 3 / present | Causes described as potential, not proven | Approved |
| FP-02 | Temperature peak 96.0 °C; over 90 °C from 14:00–16:00 | Findings concern temperature only | 2 / present | Summary typo `96°Ccars`; `missing_information` unnecessarily discusses normal vibration 2.63 mm/s as an increase | Approved with caveat |
| HP-02 | Pressure up to 238 bar; high-pressure context | Yes | 3 / present | Cause remains unconfirmed | Approved |
| APU-01 | Reservoirs 6.284 bar; TP3 6.286 bar (approximately 6.28); alarm peak 100%; compressor-loading context per source | Findings concern recorded pressure/alarm anomalies | 3 / present | Some possible-cause phrases could be more expressly tentative | Approved with caveat |

**Banned-word scan:** no occurrences of `predict`, `guaranteed`, or `autonomous` in the four final explanation texts. Every report has at least one finding, two recommended checks, and a populated uncertainty sentence. All citations passed evidence-ID validation. The observed measurements above are consistent with Member 1's reference values; not every claim has been independently re-derived from raw telemetry.

**Limitations accepted by Member 1:** The FP-02 typo/vibration aside and APU-01 hedging are tolerable for this submission; regenerate neither report, since outputs must remain genuine AMD text.

### Saved-mode functionality (previously verified)

An earlier task run proved that `LLM_PROVIDER=saved` served an existing genuine AMD HP-01 explanation with provenance `saved`, grounding 1.0, unsupported 0, explanation present, and no error. The v3 saving script produced the four newer JSON artifacts; a new saved-mode endpoint test for those **specific v3 files has not been separately recorded**, so do not claim that test was performed.

## 7. AMD spending, request limits, and safety

The following is the **recorded authenticated `/usage` snapshot after Task 5, before Task 6**, not a current total:

| Measure | Recorded snapshot |
|---|---:|
| HTTP status | 200 |
| Shared daily budget | USD 1.00 |
| Daily spent | USD 0.00359321222640574 |
| Daily remaining | USD 0.9964067877735943 |
| Requests in the reported usage window | 14 |
| Prompt tokens | 17,279 |
| Completion tokens | 6,075 |
| Recorded errors | 0 |
| Rate limit | 20 requests/minute |

**No newer `/usage` snapshot was provided after the v3 generation run.** Costs may vary per request, and client-side retries may increase usage. AMD requests were issued sequentially with spacing; there is no need to issue more live calls for approved Task 6 reports.

**Safety and auditability:**

- The local key stays only in ignored `backend/.env`, and Git checks did not list that file.
- The model is instructed to cite evidence IDs; verifier checks IDs and reports unsupported references.
- **100% grounding means IDs exist, not that the sentences or root causes are infallible.**
- The system distinguishes live AMD reports (`amd_token_factory`), stored genuine AMD reports (`saved`), and local mock explanations (`mock`).
- The model provides technician decision support, not autonomous industrial control. Suggestions are human inspection checks and should follow site safety procedures.
- The exact hosting hardware cannot be independently established from the provenance label alone.

## 8. Screenshots, presentation, and sign-off

| Screenshot / supporting evidence | Current status | Safety / purpose |
|---|---|---|
| AMD dashboard access or model catalog | TODO | Hide key, authorization and sensitive account identifiers |
| Task 3 smoke test | Results recorded; screenshot TODO | Show valid JSON, latency and grounding |
| Task 4 model comparison | Results recorded; screenshot TODO | Show all six test results |
| Task 5 `TASK 5 RESULT` terminal block | Results recorded; screenshot TODO | Four HTTP 200 requests and provenance |
| AMD `/usage` view | Snapshot recorded; screenshot TODO | Hide key, account identifiers |
| Task 6 v3 console and four-report audit | JSON files and ZIP prepared; screenshot TODO | Approved v3, not superseded versions |
| `LLM_PROVIDER=saved` API check | Earlier proof recorded; screenshot TODO | Do not represent earlier run as a fresh v3 verification |
| Website AMD provenance badge | TODO | Use backend provenance; do not hardcode an unverified accelerator claim |
| Git security check | Previous checks passed; final PR safety review TODO | Never stage or commit `.env` |

**Member 1 handoff:** `ForgeGuard_Task6_v3.zip`, Task 6 v3 audit table, this `AMD_EVIDENCE.md`, and (after Task 8) `backend/tests/test_ai.py`. The authorized `m2-ai` pull request may stage only `data/demo_reports/`, `docs/AMD_EVIDENCE.md`, and `backend/tests/test_ai.py`. **Do not stage** `prompts.py`, `verify.py`, `.env`, or the local ZIP; **open the PR but do not merge**.

**Task 6 sign-off:** Approved by Member 1.  
**Task 7 sign-off:** Draft updated; screenshots and Member 1 document review pending.  
**Task 8:** To be developed using fake/mock transport, with no real AMD requests.
