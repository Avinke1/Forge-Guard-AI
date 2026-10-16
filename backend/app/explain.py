"""Steps 5-6 glue: turn ONE machine case into an InspectionReport (CLAUDE.md sections 5.5, 5.6, 6).

Member 2's files do the AI work and are used unchanged:
  llm_client.AMDTokenFactoryClient   one OpenAI-compatible chat call (AMD Token Factory)
  prompts.build_messages             system + user prompt from the case dict built here
  verify.verify_report               evidence-ID check + grounding rate
  reports.ReportGenerator            one call + one JSON repair, rule-based fallback
This module (Member 1) adds what the API contract needs:
  - the case sent to the AI holds ONLY evidence: anomalies, notes LINKED to them, up to 12 key reading
    rows with real sensor values, and matching fault_action_table rows ("general guidance, not
    manufacturer-verified"). Never the label column, never fault_events.csv.
  - no AI call for a machine without anomalies (nothing to explain)
  - provider "mock": deterministic fake explanation, labelled MOCK - not AI output
  - InspectionReport shape: on any failure explanation = null, provenance = null, grounding_rate = null,
    error = plain message, fallback_summary = "Rule-based summary (no AI): ..." built only from
    anomalies and notes
  - saved demo reports (data/demo_reports/<dataset>/<machine>.json) when the AI is unavailable
  - cache per run_id + machine_id; llm_status() health check cached 30 s
"""

import csv
import json
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

from backend.app import llm_client, reports, verify
from backend.app.schemas import (
    AIExplanation,
    AnalysisResult,
    InspectionReport,
    LLMStatus,
    MachineCase,
    Provenance,
    Reading,
    UnsupportedItem,
)
from backend.app.settings import REPO_ROOT, get_settings
from backend.app.store import StoredRun

FAULT_ACTION_TABLE = REPO_ROOT / "knowledge" / "fault_action_table.csv"
SAVED_REPORTS_DIR = REPO_ROOT / "data" / "demo_reports"
GUIDANCE_LABEL = "general guidance, not manufacturer-verified"
MAX_KEY_READINGS = 12
MOCK_HARDWARE_LABEL = "none - MOCK mode, no AI model was called"
STATUS_TTL_S = 30.0
CACHE_SIZE = 200

# fault_action_table.csv "source" per dataset, and which rows belong to which sensor.
_GUIDANCE_SOURCE = {"synthetic_fleet": "Synthetic fleet", "metropt3": "MetroPT-3"}
_GUIDANCE_PREFIX = {
    "vibration_mm_s": "Vibration",
    "temperature_c": "Temperature",
    "pressure_bar": "Pressure",
    "sound_db": "Sound",
    "rpm": "RPM",
}

_cache: "OrderedDict[tuple[str, str], InspectionReport]" = OrderedDict()
_cache_lock = threading.Lock()
_status: tuple[float, LLMStatus] | None = None
_status_lock = threading.Lock()


# ---------------------------------------------------------------- case for the AI


def _guidance_rows() -> list[dict[str, str]]:
    with FAULT_ACTION_TABLE.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def guidance_for(dataset_id: str, sensors: set[str]) -> list[dict[str, str]]:
    source = _GUIDANCE_SOURCE.get(dataset_id)
    if source is None:
        return []
    prefixes = {_GUIDANCE_PREFIX[s] for s in sensors if s in _GUIDANCE_PREFIX}
    out = []
    for row in _guidance_rows():
        if row.get("source") != source:
            continue
        if prefixes and not any(row.get("fault_or_condition", "").startswith(p) for p in prefixes):
            continue
        out.append(
            {
                "fault_or_condition": row.get("fault_or_condition", ""),
                "signal_or_evidence": row.get("signal_or_evidence", ""),
                "meaning": row.get("meaning", ""),
                "action": row.get("action", ""),
                "guidance": GUIDANCE_LABEL,
            }
        )
    return out


def _peak_row_id(anomaly, rows: dict[str, Reading]) -> str:
    best, best_diff = anomaly.row_ids[0], float("inf")
    for rid in anomaly.row_ids:
        value = rows[rid].model_dump().get(anomaly.sensor) if rid in rows else None
        if value is not None and abs(value - anomaly.peak) < best_diff:
            best, best_diff = rid, abs(value - anomaly.peak)
    return best


def key_reading_ids(case: MachineCase, rows: dict[str, Reading]) -> list[str]:
    """First, peak and last row of each anomaly (in queue order), max 12, sorted by time."""
    picked: list[str] = []
    for a in case.anomalies:
        for rid in (a.row_ids[0], _peak_row_id(a, rows), a.row_ids[-1]):
            if rid not in picked:
                picked.append(rid)
    picked = picked[:MAX_KEY_READINGS]
    return sorted(picked, key=lambda rid: (rows[rid].timestamp, rid) if rid in rows else (datetime.max, rid))


def build_llm_case(result: AnalysisResult, case: MachineCase) -> dict:
    """The ONLY data the AI sees for one machine. Allowed evidence IDs == case.evidence_ids."""
    rows = {r.row_id: r for r in result.readings if r.machine_id == case.machine_id}
    linked = {l.note_id for a in case.anomalies for l in a.linked_notes}
    key_rows = []
    for rid in key_reading_ids(case, rows):
        if rid in rows:
            row = rows[rid].model_dump(mode="json")
            row.pop("label", None)  # never present after validation; defensive
            key_rows.append(row)
    return {
        "machine_id": case.machine_id,
        "priority": case.priority,
        "score": case.score,
        "anomalies": [a.model_dump(mode="json") for a in case.anomalies],
        "notes": [n.model_dump(mode="json") for n in case.notes if n.note_id in linked],
        "key_readings": key_rows,
        "guidance": guidance_for(result.dataset.id, {a.sensor for a in case.anomalies}),
        "dataset": {"id": result.dataset.id, "synthetic": result.dataset.synthetic},
    }


# ---------------------------------------------------------------- rule-based fallback


def fallback_summary(case: MachineCase) -> str:
    parts = [f"Rule-based summary (no AI): {case.machine_id} - priority {case.priority} (score {case.score:g})."]
    if not case.anomalies:
        parts.append("No anomalies were detected for this machine.")
        quality = [c for c in case.context if c.kind != "transient_ignored"]
        if quality:
            parts.append(f"{len(quality)} data-quality warning(s) - see the machine page.")
        return " ".join(parts)
    for a in case.anomalies:
        parts.append(f"{a.anomaly_id}: {a.reason}")
    notes = {n.note_id: n for n in case.notes}
    linked = list(dict.fromkeys(l.note_id for a in case.anomalies for l in a.linked_notes))
    if linked:
        parts.append(
            "Linked notes: "
            + " ".join(f"{nid} ({notes[nid].timestamp:%Y-%m-%d %H:%M}, {notes[nid].source}): {notes[nid].text}"
                       for nid in linked if nid in notes)
        )
    parts.append("This summary lists the detected evidence only; it does not state a cause.")
    return " ".join(parts)


def _error_report(case: MachineCase, message: str) -> InspectionReport:
    return InspectionReport(
        machine_id=case.machine_id,
        explanation=None,
        unsupported=[],
        grounding_rate=None,
        provenance=None,
        error=message,
        fallback_summary=fallback_summary(case),
    )


def _to_report(case: MachineCase, checked: dict, unsupported: list[dict], grounding: float,
               provenance: Provenance) -> InspectionReport:
    return InspectionReport(
        machine_id=case.machine_id,
        explanation=AIExplanation.model_validate(checked),  # extra verify keys per item are ignored
        unsupported=[UnsupportedItem(section=u["section"], index=u["index"]) for u in unsupported],
        grounding_rate=grounding,
        provenance=provenance,
        error=None,
        fallback_summary=None,
    )


# ---------------------------------------------------------------- providers


def _mock_report(case: MachineCase, llm_case: dict) -> InspectionReport:
    start = time.perf_counter()
    rows = {r["row_id"]: r for r in llm_case["key_readings"]}
    notes = {n["note_id"]: n for n in llm_case["notes"]}
    findings, causes, checks = [], [], []
    cited_notes: set[str] = set()
    for a in llm_case["anomalies"][:5]:
        peak_rows = [rid for rid in a["row_ids"] if rid in rows and rows[rid].get(a["sensor"]) == a["peak"]]
        findings.append({"statement": a["reason"], "evidence": [a["anomaly_id"], *peak_rows[:1]]})
        for link in a["linked_notes"]:
            if link["note_id"] in notes and link["note_id"] not in cited_notes:
                cited_notes.add(link["note_id"])
                causes.append({
                    "cause": f"MOCK: possibly related to note {link['note_id']} ({link['relation']} the anomaly).",
                    "evidence": [a["anomaly_id"], link["note_id"]],
                })
                break
    for g in llm_case["guidance"][:3]:
        first = llm_case["anomalies"][0]["anomaly_id"]
        checks.append({"action": f"{g['action']} ({GUIDANCE_LABEL})", "reason": f"MOCK: {g['fault_or_condition']}",
                       "evidence": [first]})
    report = {
        "machine_id": case.machine_id,
        "summary": f"MOCK - not AI output. {case.machine_id} has {len(case.anomalies)} anomaly record(s); "
                   f"priority {case.priority}.",
        "findings": findings,
        "possible_causes": causes,
        "recommended_checks": checks,
        "missing_information": ["MOCK mode: no AI model was called."],
        "uncertainty": "MOCK output for interface testing only; it is not an AI explanation.",
    }
    v = verify.verify_report(report, llm_case)
    provenance = Provenance(
        provider="mock", model="mock", hardware_label=MOCK_HARDWARE_LABEL,
        latency_ms=round((time.perf_counter() - start) * 1000, 1), created_at=datetime.now(timezone.utc), cached=False,
    )
    return _to_report(case, v.checked_report, v.unsupported_claims, v.grounding_rate, provenance)


def make_client() -> llm_client.AMDTokenFactoryClient:
    """Member 2's client; reads AMD_TOKEN_FACTORY_* from the environment (settings.py exports .env)."""
    return llm_client.AMDTokenFactoryClient(timeout_s=get_settings().llm_timeout_s)


def _amd_report(case: MachineCase, llm_case: dict) -> InspectionReport:
    try:
        generator = reports.ReportGenerator(make_client())
    except llm_client.LLMError as exc:  # e.g. missing or non-HTTPS base URL
        return _error_report(case, str(exc))
    out = generator.generate(llm_case)
    if out.get("report_status") == "rule_based_fallback" or out.get("error"):
        return _error_report(case, out.get("error") or "The AI explanation is unavailable.")
    p = out["provenance"]
    provenance = Provenance(
        provider="amd_token_factory",
        model=str(p.get("model", "")),
        hardware_label=str(p.get("hardware_label", "")),
        latency_ms=p.get("latency_ms"),
        created_at=p.get("created_at") or datetime.now(timezone.utc),
        cached=False,
    )
    return _to_report(case, out["explanation"], out["unsupported_claims"], out["grounding_rate"], provenance)


def load_saved_report(dataset_id: str, machine_id: str) -> InspectionReport | None:
    path = SAVED_REPORTS_DIR / dataset_id / f"{machine_id}.json"
    if not path.is_file():
        return None
    try:
        report = InspectionReport.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, OSError):
        return None
    if report.explanation is None or report.provenance is None:
        return None
    report.provenance = report.provenance.model_copy(update={"provider": "saved", "cached": True})
    return report


# ---------------------------------------------------------------- entry points


def explain_machine(run: StoredRun, machine_id: str) -> InspectionReport:
    """InspectionReport for one machine of a stored run. Raises KeyError if the machine is not in the run."""
    result = run.result
    case = next((c for c in result.cases if c.machine_id == machine_id), None)
    if case is None:
        raise KeyError(machine_id)

    key = (result.run_id, machine_id)
    with _cache_lock:
        cached = _cache.get(key)
    if cached is not None:
        if cached.provenance is None:
            return cached
        return cached.model_copy(update={"provenance": cached.provenance.model_copy(update={"cached": True})})

    if not case.anomalies:
        report = _error_report(case, "No anomalies were detected for this machine, so there is nothing for the AI "
                                     "to explain.")
    else:
        llm_case = build_llm_case(result, case)
        provider = get_settings().llm_provider
        if provider == "mock":
            report = _mock_report(case, llm_case)
        elif provider == "amd_token_factory":
            report = _amd_report(case, llm_case)
            if report.explanation is None and run.is_demo:
                report = load_saved_report(result.dataset.id, machine_id) or report
        else:
            report = _error_report(case, f"LLM provider '{provider}' is not connected in this backend.")

    if report.explanation is not None:  # only successful reports are cached; failures may be retried
        with _cache_lock:
            _cache[key] = report
            while len(_cache) > CACHE_SIZE:
                _cache.popitem(last=False)
    return report


def llm_status() -> LLMStatus:
    """Real health check of the configured provider, cached 30 s. Never returns keys or URLs."""
    global _status
    with _status_lock:
        if _status is not None and time.monotonic() - _status[0] < STATUS_TTL_S:
            return _status[1]
    provider = get_settings().llm_provider
    if provider == "mock":
        status = LLMStatus(provider="mock", model="mock", hardware_label=MOCK_HARDWARE_LABEL, reachable=True,
                           last_latency_ms=0.0, error=None)
    elif provider == "amd_token_factory":
        status = _amd_status()
    else:
        status = LLMStatus(provider=provider, model="", hardware_label="", reachable=False,
                           error=f"LLM provider '{provider}' is not connected in this backend.")
    with _status_lock:
        _status = (time.monotonic(), status)
    return status


def _amd_status() -> LLMStatus:
    hardware = llm_client.Completion.__dataclass_fields__["hardware_label"].default
    try:
        client = make_client()
    except llm_client.LLMError as exc:
        return LLMStatus(provider="amd_token_factory", model="", hardware_label=hardware, reachable=False, error=str(exc))
    try:
        c = client.complete([{"role": "user", "content": "Reply with the single word OK."}], max_tokens=5)
    except (llm_client.LLMError, ValueError) as exc:
        return LLMStatus(provider="amd_token_factory", model=client.model, hardware_label=hardware, reachable=False,
                         error=str(exc))
    return LLMStatus(provider="amd_token_factory", model=c.model, hardware_label=c.hardware_label, reachable=True,
                     last_latency_ms=float(c.latency_ms), error=None)


def clear_caches() -> None:
    global _status
    with _cache_lock:
        _cache.clear()
    with _status_lock:
        _status = None
