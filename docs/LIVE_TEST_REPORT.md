# ForgeGuard AI - Live Acceptance Test Report

- **Date/time:** Sun 18 Oct 2026, 12:30 PM
- **Browser / device:** Windows
- **Tester:** Anthony Fernandes (Member 5)
- **Site:** https://forge-guard-ai.vercel.app

## Results

| ID | Check | Expected | Result | Notes |
|---|---|---|---|---|
| A1 | /api/health | status ok, version 0.1.0 | PASS | Returned exactly that |
| A2 | /api/datasets | 2 datasets: synthetic_fleet (true), metropt3 (false) | PASS | Both present; attribution text correct |
| A3 | /api/llm/status | amd_token_factory, reachable true, error null | PASS | DeepSeek-V4-Flash, latency ~1.2 s |
| A4 | /docs | Swagger page opens | PASS | ForgeGuard AI API - Swagger UI |
| B1 | No MOCK DATA banner | No yellow banner | PASS | Tester-reported PASS |
| B2 | Menu pages | Overview, Upload, Queue, History, AI Status open | PASS | Tester-reported PASS |
| B3 | F5 on /queue and /status | Still loads, no 404 | PASS | Tester-reported PASS |
| B4 | Console errors (F12) | No red errors | PASS | Tester-reported PASS |
| B5 | AI Status page | Reachable Yes, amd_token_factory, DeepSeek-V4-Flash, AMD label, error - | PASS | Tester-reported PASS |
| B6 | Phone view | Readable, menu works, no sideways scroll | PASS | Tester-reported PASS |
| C1 | Run demo: synthetic fleet | Opens Queue (up to ~60 s first time) | PASS | Tester-reported PASS |
| C2 | Synthetic label | Clearly labelled SYNTHETIC | PASS | Tester-reported PASS |
| C3 | Queue order | HP-01 HIGH, FP-02 HIGH, HP-02 MEDIUM, DS-02 LOW, DS-01 OK, FP-01 OK | PASS | Tester-reported PASS |
| C4 | What ForgeGuard did panel | 6 machines, HIGH 2 / MED 1 / LOW 1 / OK 2, Inspect first: HP-01 | PASS | Tester-reported PASS |
| C5 | Search box | HP-01, HIGH, vibration, xyz, clear button | PASS | Tester-reported PASS |
| C6 | Voice search | HP-01 opens; 'high' fills box; mic blocked gives clear error | PASS | Tester-reported PASS |
| C7 | HP-01 page | Charts, unusual readings, maintenance notes | PASS | Tester-reported PASS |
| C8 | REAL AMD CALL #1 (HP-01) | Explanation, AMD badge, chips, drawer; ~8.0 mm/s, ~90 dB | PASS | Once only; Tester-reported PASS |
| C9 | FP-01 (OK machine) | Rule-based summary, no AI request | PASS | Tester-reported PASS |
| C10 | Upload > Run demo | Goes to Queue automatically | PASS | Tester-reported PASS |
| D1 | Run demo: MetroPT-3 | Queue shows APU-01 HIGH | PASS | Tester-reported PASS |
| D2 | Real data label | UCI, CC BY 4.0 attribution | PASS | Tester-reported PASS |
| D3 | APU-01 readings | Unusual on 15 Jul 2020, ~16:55-18:45 | PASS | Tester-reported PASS |
| D4 | REAL AMD CALL #2 (APU-01) | ~6.28 bar, alarm signal 100 % | PASS | Last AMD call; Tester-reported PASS |
| E1 | Add evidence: photo | Thumbnail shown | PASS | Tester-reported PASS |
| E2 | Video (mp4) | Plays | PASS | Tester-reported PASS |
| E3 | Audio (mp3) | Plays | PASS | Tester-reported PASS |
| E4 | Text (.txt) | Text shown | PASS | Tester-reported PASS |
| E5 | PDF | Opens in new tab | PASS | Tester-reported PASS |
| E6 | Image over 10 MB | Rejected with clear message | PASS | Tester-reported PASS |
| E7 | Disallowed (.exe/.zip) | Rejected | PASS | Tester-reported PASS |
| E8 | 9th file | 'max 8' message | PASS | Tester-reported PASS |
| E9 | F5 refresh | Files still there | PASS | Tester-reported PASS |
| E10 | Remove | Gone after refresh | PASS | Tester-reported PASS |
| E11 | Privacy text | 'Saved on this device only... Not sent to the AI' visible | PASS | Tester-reported PASS |
| F1 | Upload .txt as readings | Clear 'Only .csv files...' error | PASS | Tester-reported PASS |
| F2 | /machines/XYZ-99 | Friendly not found, no crash | PASS | Tester-reported PASS |
| F3 | History page | Runs listed, newest first | PASS | Tester-reported PASS |
| G1 | Banned words | predict/predictive/prediction/autonomous/guaranteed: none | PASS | Tester-reported PASS |
| G2 | Footer | 'A qualified technician makes the decision.' | PASS | Tester-reported PASS |
| G3 | AMD badge | Only on real AMD answers | PASS | Tester-reported PASS |

## AMD numbers

| Machine | Time (s) | Grounding % | Unsupported items |
|---|---|---|---|
| HP-01 | not recorded | not recorded | not recorded |
| APU-01 | not recorded | not recorded | not recorded |

## Problems found

| What | Where | Steps to repeat | Screenshot |
|---|---|---|---|
| None | | | |

## Summary

**41 of 41 PASS** (Part A checked against the live API; B-G tested in the browser by Anthony Fernandes).
