"""Real evaluation numbers for the judges -> docs/EVALUATION.md (CLAUDE.md section 10).

Run from the repo root:
    .venv/Scripts/python.exe scripts/evaluate.py
Optional: --out <path> to write the report somewhere else (used by the test suite).

The "label" column and fault_events.csv are read HERE ONLY, as the answer key. The pipeline never sees them:
validation removes "label" before detection, and fault_events.csv is not an input of any pipeline step.
Every number in the report comes from this run. Nothing is rounded up or typed in by hand.
"""

import argparse
import json
import platform
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import pandas as pd  # noqa: E402

from backend.app.datasets import get_dataset, load_demo_frames, read_csv_as_text  # noqa: E402
from backend.app.pipeline import analyze  # noqa: E402
from backend.app.schemas import InspectionReport  # noqa: E402

EVENT_LEAD = timedelta(hours=2)  # an anomaly up to 2 h before a failure window counts as detecting it
EPISODE_MERGE_GAP = timedelta(hours=1)  # anomalies (any sensor) closer than this form one alert episode
HOLDOUT_START = datetime(2020, 7, 1)  # thresholds were tuned on Feb-Jun 2020 (F1-F3); F4 is held out
SAVED_REPORTS_DIR = REPO / "data" / "demo_reports"


def _ts(value) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M")


def _prf(flagged: set[str], positives: set[str]) -> dict:
    tp = len(flagged & positives)
    fp = len(flagged - positives)
    fn = len(positives - flagged)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "flagged": len(flagged), "positives": len(positives),
            "precision": precision, "recall": recall, "f1": f1}


def _label_positives(readings_path: Path) -> set[str]:
    """Row IDs with label=1, using the same numbering as validation (R1 = first data row)."""
    raw = read_csv_as_text(readings_path)
    return {f"R{i + 1}" for i, v in enumerate(raw["label"].str.strip()) if v == "1"}


# ---------------------------------------------------------------- a) synthetic fleet acceptance


def synthetic_acceptance() -> dict:
    readings, notes = load_demo_frames("synthetic_fleet")
    bundle = analyze(readings, notes, "synthetic_fleet")
    r = bundle.result
    cases = {c.machine_id: c for c in r.cases}
    order = [c.machine_id for c in r.cases]

    def limit(mid, sensor):
        return [a for a in cases[mid].anomalies if a.sensor == sensor and a.method == "limit"]

    def covers(anoms, start, end):
        return any(a.start <= start and a.end >= end for a in anoms)

    D = datetime
    warnings = " | ".join(r.validation.warnings)
    checks = []

    def check(machine, expected, ok, observed):
        checks.append({"machine": machine, "expected": expected, "observed": observed, "pass": bool(ok)})

    hp01 = cases["HP-01"]
    v, s = limit("HP-01", "vibration_mm_s"), limit("HP-01", "sound_db")
    check("HP-01", "bearing wear: vibration + sound flagged from 16 Oct 08:00, HIGH, first in queue",
          v and s and v[0].start == D(2026, 10, 16, 8) and s[0].start == D(2026, 10, 16, 8)
          and hp01.priority == "HIGH" and order[0] == "HP-01",
          f"{hp01.priority} {hp01.score}, rank {order.index('HP-01') + 1}; vibration from "
          f"{_ts(v[0].start) if v else '-'}, sound from {_ts(s[0].start) if s else '-'}")
    fp02 = cases["FP-02"]
    check("FP-02", "overheating 15 Oct 14:00-16:00 flagged, HIGH or MEDIUM",
          covers(limit("FP-02", "temperature_c"), D(2026, 10, 15, 14), D(2026, 10, 15, 16))
          and fp02.priority in ("HIGH", "MEDIUM"),
          f"{fp02.priority} {fp02.score}; temperature anomalies: "
          + ", ".join(f"{_ts(a.start)}-{a.end:%H:%M} ({a.method})" for a in fp02.anomalies))
    hp02 = cases["HP-02"]
    check("HP-02", "overpressure 16 Oct 11:00-12:00 flagged, MEDIUM or HIGH",
          covers(limit("HP-02", "pressure_bar"), D(2026, 10, 16, 11), D(2026, 10, 16, 12))
          and hp02.priority in ("MEDIUM", "HIGH"),
          f"{hp02.priority} {hp02.score}; pressure anomalies: "
          + ", ".join(f"{_ts(a.start)}-{a.end:%H:%M} ({a.method})" for a in hp02.anomalies))
    ds01 = cases["DS-01"]
    ignored = [c for c in ds01.context if c.kind == "transient_ignored"]
    check("DS-01", "one spike 15 Oct 10:15 NOT flagged (one-off spike ignored)",
          not ds01.anomalies and ds01.priority == "OK" and ignored,
          f"{ds01.priority}; {len(ds01.anomalies)} anomalies; ignored spike shown as context "
          f"with notes {ignored[0].note_ids if ignored else []}")
    ds02 = cases["DS-02"]
    kinds = [c.kind for c in ds02.context]
    check("DS-02", "messy data: warnings only (3 empty cells, rpm -50 sensor error, gap), LOW or OK, not HIGH",
          not ds02.anomalies and ds02.priority in ("LOW", "OK") and kinds.count("empty_cell") == 3
          and "sensor_error" in kinds and "gap" in kinds and "SENSOR ERROR: DS-02 rpm = -50" in warnings,
          f"{ds02.priority}; {len(ds02.anomalies)} anomalies; context: {kinds.count('empty_cell')} empty cells, "
          f"{kinds.count('sensor_error')} sensor error, {kinds.count('gap')} gap")
    fp01 = cases["FP-01"]
    check("FP-01", "normal -> OK", not fp01.anomalies and fp01.priority == "OK",
          f"{fp01.priority}; {len(fp01.anomalies)} anomalies")

    flagged = {rid for c in r.cases for a in c.anomalies for rid in a.row_ids}
    positives = _label_positives(get_dataset("synthetic_fleet").readings_path)
    rows = _prf(flagged, positives)
    # Where are the flagged rows with label 0? Grouped per anomaly, so the report can say exactly.
    extra = []
    for c in r.cases:
        for a in c.anomalies:
            fp = [rid for rid in a.row_ids if rid not in positives]
            if fp:
                extra.append(f"{c.machine_id} {a.sensor} ({a.method}) {len(fp)} row(s) from {_ts(a.start)}")
    rows["label0_flags"] = extra
    return {"checks": checks, "queue": [(c.machine_id, c.priority, c.score) for c in r.cases], "rows": rows}


# ---------------------------------------------------------------- b) MetroPT-3 full history


def _episodes(anomalies) -> list[dict]:
    spans = sorted((a.start, a.end) for a in anomalies)
    out: list[dict] = []
    for start, end in spans:
        if out and start <= out[-1]["end"] + EPISODE_MERGE_GAP:
            out[-1]["end"] = max(out[-1]["end"], end)
            out[-1]["n"] += 1
        else:
            out.append({"start": start, "end": end, "n": 1})
    return out


def _matches(start, end, ev) -> bool:
    return start <= ev.end and end >= ev.start - EVENT_LEAD


def metropt_evaluation() -> dict:
    ds = get_dataset("metropt3")
    raw = read_csv_as_text(ds.full_readings_path)
    bundle = analyze(raw, None, ds, include_readings=False)
    anomalies = bundle.result.cases[0].anomalies
    events = pd.read_csv(ds.extra_paths["fault_events"], parse_dates=["start", "end"])  # ANSWER KEY

    rows = []
    for ev in events.itertuples():
        hits = [a for a in anomalies if _matches(a.start, a.end, ev)]
        first = min((a.start for a in hits), default=None)
        rows.append({
            "event": ev.event_id, "start": ev.start, "end": ev.end, "detected": bool(hits),
            "first_alert": first,
            "lead_h": None if first is None else (first - ev.start).total_seconds() / 3600,
            "anomalies": len(hits), "sensors": sorted({a.sensor for a in hits}),
            "split": "held-out" if ev.start >= HOLDOUT_START else "tuning",
        })

    times = bundle.validation.readings["timestamp"]
    t0, t1 = times.min(), times.max()
    periods = {
        "all": (t0, t1),
        "tuning (Feb-Jun 2020)": (t0, pd.Timestamp(HOLDOUT_START)),
        "held-out (Jul-Sep 2020)": (pd.Timestamp(HOLDOUT_START), t1),
    }

    def false_counts(start, end):
        weeks = (end - start).total_seconds() / (7 * 86400)
        anoms = [a for a in anomalies if start <= a.start < end]
        fa = [a for a in anoms if not any(_matches(a.start, a.end, ev) for ev in events.itertuples())]
        eps = [e for e in _episodes(anoms)]
        fe = [e for e in eps if not any(_matches(e["start"], e["end"], ev) for ev in events.itertuples())]
        return {"weeks": weeks, "anomalies": len(anoms), "false_anomalies": len(fa),
                "false_anomalies_per_week": len(fa) / weeks if weeks else 0.0,
                "episodes": len(eps), "false_episodes": len(fe),
                "false_episodes_per_week": len(fe) / weeks if weeks else 0.0}

    false_alarms = {name: false_counts(s, e) for name, (s, e) in periods.items()}

    demo_readings, demo_notes = load_demo_frames("metropt3")
    demo = analyze(demo_readings, demo_notes, "metropt3").result
    f4 = events[events.event_id == "F4"].iloc[0]
    demo_case = demo.cases[0]
    demo_f4 = [a for a in demo_case.anomalies if _matches(a.start, a.end, f4)]
    skipped = int(bundle.validation.readings["skip_detection"].sum())
    return {
        "events": rows, "false_alarms": false_alarms, "span": (t0, t1), "windows": len(times),
        "skipped_windows": skipped, "total_anomalies": len(anomalies),
        "demo": {"priority": demo_case.priority, "score": demo_case.score, "anomalies": len(demo_case.anomalies),
                 "f4_anomalies": len(demo_f4)},
        "params": {"window": ds.zscore_window, "threshold": ds.zscore_threshold, "min_consecutive": ds.min_consecutive,
                   "min_raw_rows": ds.min_raw_rows},
    }


# ---------------------------------------------------------------- c) AI4I


def ai4i_evaluation() -> dict:
    ds = get_dataset("ai4i")
    bundle = analyze(read_csv_as_text(ds.readings_path), None, ds, include_readings=False)
    flagged = {rid for c in bundle.result.cases for a in c.anomalies for rid in a.row_ids}
    rows = _prf(flagged, _label_positives(ds.readings_path))
    rows["anomalies"] = sum(len(c.anomalies) for c in bundle.result.cases)
    rows["rows"] = bundle.result.validation.rows_kept
    rows["params"] = {"window": ds.zscore_window, "threshold": ds.zscore_threshold,
                      "min_consecutive": ds.min_consecutive}
    return rows


# ---------------------------------------------------------------- d) AI explanations (saved AMD reports)


def ai_reports() -> dict:
    files = sorted(SAVED_REPORTS_DIR.glob("*/*.json")) if SAVED_REPORTS_DIR.is_dir() else []
    reports, invalid = [], []
    for path in files:
        try:
            reports.append((path, InspectionReport.model_validate(json.loads(path.read_text(encoding="utf-8")))))
        except (ValueError, OSError):
            invalid.append(path)
    with_ai = [(p, r) for p, r in reports if r.explanation is not None and r.provenance is not None]
    amd = [(p, r) for p, r in with_ai if r.provenance.provider not in ("mock", "saved")]
    grounding = [r.grounding_rate for _, r in amd if r.grounding_rate is not None]
    latency = [r.provenance.latency_ms for _, r in amd if r.provenance.latency_ms is not None]
    return {
        "files": len(files), "valid": len(reports), "invalid": len(invalid), "with_explanation": len(with_ai),
        "amd": len(amd),
        "providers": sorted({r.provenance.provider for _, r in with_ai}),
        "models": sorted({r.provenance.model for _, r in amd}),
        "grounding_mean": sum(grounding) / len(grounding) if grounding else None,
        "grounding_min": min(grounding) if grounding else None,
        "latency_mean_ms": sum(latency) / len(latency) if latency else None,
        "per_report": [(p.parent.name, p.stem, r.grounding_rate, r.provenance.latency_ms) for p, r in amd],
    }


# ---------------------------------------------------------------- report


def _pct(x: float) -> str:
    return f"{100 * x:.1f} %"


def render(syn: dict, met: dict, ai4i: dict, ai: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    L: list[str] = []
    add = L.append
    add("# ForgeGuard AI - Evaluation (real numbers)")
    add("")
    add(f"Generated by `scripts/evaluate.py` on {now} (Python {platform.python_version()}). "
        "Re-run it to reproduce every number below. The `label` column and `fault_events.csv` are used "
        "here only, as the answer key; the pipeline never sees them.")
    add("")
    add("ForgeGuard does not predict failures. It flags unusual readings with rules + statistics "
        "(limits and a z-score against each machine's own past) and ranks machines for inspection.")
    add("")

    passed = sum(c["pass"] for c in syn["checks"])
    add(f"## a) Synthetic fleet - planted cases: {passed}/{len(syn['checks'])} PASS")
    add("")
    add("SYNTHETIC demo data - not real plant measurements.")
    add("")
    add("| Machine | Expected | Result | What the backend found |")
    add("|---|---|---|---|")
    for c in syn["checks"]:
        add(f"| {c['machine']} | {c['expected']} | {'PASS' if c['pass'] else 'FAIL'} | {c['observed']} |")
    add("")
    add("Inspection queue: " + " > ".join(f"{m} {p} ({s:g})" for m, p, s in syn["queue"]))
    add("")
    rr = syn["rows"]
    add(f"Row level vs `label` (extra, for transparency): {rr['flagged']} rows flagged, {rr['positives']} labelled 1 - "
        f"precision {_pct(rr['precision'])}, recall {_pct(rr['recall'])}, F1 {rr['f1']:.3f} "
        f"(TP {rr['tp']}, FP {rr['fp']}, FN {rr['fn']}). Flagged rows with label 0: "
        + ("; ".join(rr["label0_flags"]) or "none")
        + ". In the data, label=1 starts only where the planted fault is fully developed, so a z-score flag on "
        "the rise before a limit is crossed counts as 'false positive' here.")
    add("")

    p = met["params"]
    add("## b) MetroPT-3 - real air compressor, full history (event level)")
    add("")
    add(f"Data: `readings_full_5min.csv`, {met['windows']:,} five-minute windows, "
        f"{_ts(met['span'][0])} to {_ts(met['span'][1])}; {met['skipped_windows']} windows with raw_rows < "
        f"{p['min_raw_rows']} skipped. Method: z-score vs the machine's previous {p['window']} windows (about 24 h), "
        f"|z| >= {p['threshold']:g}, held for at least {p['min_consecutive']} consecutive windows (1 h). "
        f"{met['total_anomalies']} anomalies in total (counted per sensor).")
    add("")
    add("**Honesty note:** the 12-window rule was chosen using Feb-Jun 2020 only (F1-F3). "
        "F4 (15 Jul 2020) was not looked at while tuning - it is the held-out check.")
    add("")
    add("Detected = an anomaly overlapping the reported failure window or starting up to 2 h before it.")
    add("")
    add("| Event | Reported window | Split | Detected | First alert | vs failure start | Anomalies | Sensors |")
    add("|---|---|---|---|---|---|---|---|")
    for e in met["events"]:
        lead = "-" if e["lead_h"] is None else f"{e['lead_h']:+.1f} h"
        first = "-" if e["first_alert"] is None else _ts(e["first_alert"])
        add(f"| {e['event']} | {_ts(e['start'])} - {_ts(e['end'])} | {e['split']} | "
            f"{'YES' if e['detected'] else 'NO'} | {first} | {lead} | {e['anomalies']} | {', '.join(e['sensors'])} |")
    add("")
    add("Negative = alert before the reported start, positive = after it.")
    add("")
    add("False alarms = anomalies outside every reported window (and its 2 h lead). Two ways of counting: per "
        "sensor (one event seen by 3 sensors = 3), and as alert episodes (anomalies on any sensor less than 1 h "
        "apart merged into one - closer to what a technician sees).")
    add("")
    add("| Period | Weeks | False anomalies | per week | False episodes | per week |")
    add("|---|---|---|---|---|---|")
    for name, f in met["false_alarms"].items():
        add(f"| {name} | {f['weeks']:.1f} | {f['false_anomalies']} | {f['false_anomalies_per_week']:.2f} | "
            f"{f['false_episodes']} | {f['false_episodes_per_week']:.2f} |")
    add("")
    add("Caution: `label=0` means 'not inside a reported window', not 'proven healthy' - some 'false alarms' may "
        "be unreported events. Only 4 events exist, so these numbers are indicative, not statistically strong.")
    add("")
    d = met["demo"]
    add(f"Demo slice (`readings.csv`, 8-16 Jul 2020): APU-01 {d['priority']} ({d['score']:g}), "
        f"{d['anomalies']} anomalies, {d['f4_anomalies']} of them on F4.")
    add("")

    add("## c) AI4I 2020 - synthetic, row level (evaluation only, not in the UI)")
    add("")
    add(f"{ai4i['rows']:,} rows, {ai4i['positives']} with label=1. Same z-score method "
        f"(previous {ai4i['params']['window']} rows, |z| >= {ai4i['params']['threshold']:g}, "
        f"{ai4i['params']['min_consecutive']} in a row); AI4I has no limits. {ai4i['anomalies']} anomalies, "
        f"{ai4i['flagged']} rows flagged.")
    add("")
    add("| Precision | Recall | F1 | TP | FP | FN |")
    add("|---|---|---|---|---|---|")
    add(f"| {_pct(ai4i['precision'])} | {_pct(ai4i['recall'])} | {ai4i['f1']:.3f} | {ai4i['tp']} | {ai4i['fp']} | "
        f"{ai4i['fn']} |")
    add("")
    add("Why this is low: AI4I rows are independent synthetic samples with artificial timestamps, so 'unusual "
        "compared with the machine's own past' and 'held for 2 readings in a row' have little meaning there. "
        "Its failures follow fixed dataset rules (e.g. power or wear x torque thresholds) that ForgeGuard does "
        "not encode. We report it to be transparent, not as a claim of accuracy.")
    add("")

    add("## d) AI explanations (AMD)")
    add("")
    if ai["amd"] == 0:
        add(f"**Not available yet.** {ai['files']} saved report file(s) in `data/demo_reports/`; "
            f"{ai['amd']} with a real AMD response. Grounding rate, valid-JSON rate and latency on AMD will be "
            "reported here after Member 2 runs `scripts/save_demo_reports.py` against the real endpoint. "
            "No AMD numbers are claimed until then.")
    else:
        add(f"{ai['amd']} saved real AI report(s) (provider(s): {', '.join(ai['providers'])}; "
            f"model(s): {', '.join(ai['models'])}). {ai['invalid']} file(s) failed to load.")
        add("")
        add(f"- Mean grounding rate: {_pct(ai['grounding_mean'])} (lowest {_pct(ai['grounding_min'])})")
        if ai["latency_mean_ms"] is not None:
            add(f"- Mean latency: {ai['latency_mean_ms'] / 1000:.1f} s")
        add("- Valid JSON rate: only stored reports are counted here; failed calls are not saved, so this rate "
            "needs the save script's own log.")
        add("")
        add("| Dataset | Machine | Grounding | Latency (ms) |")
        add("|---|---|---|---|")
        for ds_id, mid, g, lat in ai["per_report"]:
            add(f"| {ds_id} | {mid} | {'-' if g is None else _pct(g)} | {'-' if lat is None else f'{lat:.0f}'} |")
    add("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=REPO / "docs" / "EVALUATION.md")
    args = parser.parse_args(argv)

    syn = synthetic_acceptance()
    met = metropt_evaluation()
    ai4i = ai4i_evaluation()
    ai = ai_reports()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(syn, met, ai4i, ai), encoding="utf-8")

    print(f"Synthetic planted cases: {sum(c['pass'] for c in syn['checks'])}/{len(syn['checks'])} PASS")
    for c in syn["checks"]:
        print(f"  {'PASS' if c['pass'] else 'FAIL'}  {c['machine']}: {c['observed']}")
    for e in met["events"]:
        lead = "" if e["lead_h"] is None else f" first alert {e['first_alert']} ({e['lead_h']:+.1f} h)"
        print(f"MetroPT {e['event']} ({e['split']}): {'YES' if e['detected'] else 'NO'}{lead}")
    for name, f in met["false_alarms"].items():
        print(f"MetroPT false alarms {name}: {f['false_anomalies_per_week']:.2f}/week per sensor, "
              f"{f['false_episodes_per_week']:.2f}/week as episodes")
    print(f"AI4I: precision {ai4i['precision']:.3f} recall {ai4i['recall']:.3f} F1 {ai4i['f1']:.3f}")
    print(f"AI reports with real AMD output: {ai['amd']}")
    print(f"Wrote {args.out}")
    return 0 if all(c["pass"] for c in syn["checks"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
