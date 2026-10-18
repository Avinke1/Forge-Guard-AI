# ForgeGuard AI

**AI maintenance assistant: which machine to inspect first, why, and what to check.
A qualified technician makes the decision.**

- **Live demo:** https://forge-guard-ai.vercel.app
- **Backend API:** https://forgeguard-backend.onrender.com/api/health
  (free hosting: the backend sleeps when idle - the first load takes about 1 minute)
- Built for the AMD Developer Hackathon: ACT III (lablab.ai), track **Intelligent Industry**.

## The problem

A factory has many machines, each with several sensors, and a pile of maintenance notes.
When something looks wrong, a maintenance technician or supervisor has to scan thousands of readings and
notes by hand to decide where to go first. That is slow, and easy to get wrong at the end of a shift.

**Who uses ForgeGuard:** the maintenance technician and the shift supervisor. ForgeGuard is decision
support - it ranks, explains and shows the evidence. Nothing happens automatically.

## How it works

```
CSV readings + maintenance notes
  -> 1 Validate   (bad rows, gaps, impossible values are reported, never hidden)
  -> 2 Detect     (rules + statistics: limits, and a z-score against the machine's own past)
  -> 3 Match notes (same machine, within 24 h of the anomaly)
  -> 4 Rank       (HIGH / MEDIUM / LOW / OK inspection queue)
  -> 5 Explain    (AI on AMD Token Factory: DeepSeek-V4-Flash, fallback MiMo-V2.6-Flash)
  -> 6 Verify     (every statement must cite evidence IDs that exist in the case)
  -> Inspection queue for the technician
```

Python finds the evidence; the AI only explains it. The AI sees one machine's anomalies, up to 12 key
readings and the notes linked to them - never the evaluation labels. Every AI statement cites evidence IDs
(`A-1` anomaly, `R123` reading row, `N-5` note) and is checked before anyone sees it.

## Features

- **Ranked inspection queue** - which machine first, with the reason in plain English.
- **Evidence chips** - click `A-…`, `R…` or `N-…` to see the exact reading or note behind a statement.
- **Verified AI explanation** - findings, possible causes, recommended checks, missing information and
  uncertainty; items without valid evidence are marked "unsupported". If the AI is unavailable, a
  rule-based summary (no AI) is shown instead - never a made-up report.
- **Search + voice search** on the queue (by machine ID, priority or sensor; voice uses the browser's own
  speech recognition in Chrome / Edge).
- **"+" evidence attachments** on each machine - images, video, audio and text/PDF from the technician.
  Saved on the device only; not sent to the AI.
- **Real and synthetic data** - real MetroPT-3 compressor data, and a 6-machine fleet clearly labelled
  **SYNTHETIC**.
- **Honest provenance** - the AI badge shows the provider and model exactly as the backend reports them.

## Results (measured - see [docs/EVALUATION.md](docs/EVALUATION.md))

| What | Result |
|---|---|
| Synthetic fleet, 6 planted cases | **6/6 PASS** (HP-01 HIGH and first, FP-02 HIGH, HP-02 MEDIUM, DS-02 LOW, DS-01 OK, FP-01 OK) |
| MetroPT-3 real air leaks F1-F4 | **4/4 detected**; F4 was held out (not used for tuning) and flagged 2.4 h after its reported start |
| False alarms (MetroPT-3, Feb-Sep 2020) | 1.58 per week counted per sensor, 0.76 per week as alert episodes |
| AI on AMD (4 real responses, 17 Oct 2026) | grounding 31 of 31 items (100 %), 0 unsupported; average latency 30.2 s |

## Honest limits

- The AI reads **text only** (anomalies, readings, notes). It does not look at attachments.
- Attachments stay **on this device** (browser storage) - they are not shared with the team or the backend.
- F4 was flagged **after** its reported start. ForgeGuard flags and explains unusual readings; it does not
  claim early warning.
- The AI4I benchmark score is low (precision 3.3 %, recall 2.4 %) - its rows are independent samples, see
  [docs/EVALUATION.md](docs/EVALUATION.md#c-ai4i-2020---synthetic-row-level-evaluation-only-not-in-the-ui).
- Only 4 real failure events exist in MetroPT-3, so the numbers are indicative, not statistically strong.
- Free hosting sleeps; runs are kept in memory and are lost when the backend restarts.
- Voice search depends on the browser's speech service (Chrome / Edge).

## Future work

- Vision and audio analysis of the attached photos, videos and recordings.
- A database for runs and attachments, shared across the team.
- Live sensor streams instead of CSV files.
- Earlier warning, tested on more real failure events.
- Work-order actions (create, assign, close) - always with human approval.

## Documentation

- [docs/RUN_LOCAL.md](docs/RUN_LOCAL.md) - run it on your own computer (macOS + Windows)
- [docs/DEPLOY.md](docs/DEPLOY.md) - deploy on Render (backend) and Vercel (frontend)
- [docs/API.md](docs/API.md) - the backend API contract with real example responses
- [docs/AMD_EVIDENCE.md](docs/AMD_EVIDENCE.md) - AMD Token Factory evidence
- [docs/EVALUATION.md](docs/EVALUATION.md) - all measured numbers and how they were made

## Data and licences

- **MetroPT-3** - real data from one metro-train air compressor, UCI Machine Learning Repository,
  CC BY 4.0 (https://archive.ics.uci.edu/dataset/791/metropt+3+dataset).
- **Synthetic fleet** - 6 machines made for this project; always labelled **SYNTHETIC** in the app.
- **AI4I 2020** - synthetic UCI dataset (CC BY 4.0), used for evaluation only.
- Details: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md), [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md).

## Team

| Name | Role |
|---|---|
| <Name> | <Role> |
| <Name> | <Role> |
| <Name> | <Role> |
| <Name> | <Role> |
| <Name> | <Role> |
| <Name> | <Role> |

## Licence

MIT - see [LICENSE](LICENSE).
