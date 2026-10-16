"""ForgeGuard AI - build the InspectionReport for one machine (cache, saved AMD reports, fallback).

main.py only needs two calls:
    reports.explain_machine(analysis_result, machine_id) -> InspectionReport dict (frozen API shape)
    reports.llm_status()                                  -> LLMStatus dict
scripts/save_demo_reports.py (Saturday) uses:
    reports.save_report(dataset_id, case, report)        -> data/demo_reports/<dataset>/<machine>.json

InspectionReport = {machine_id, explanation, unsupported, grounding_rate, provenance, error, fallback_summary}
  * AI worked        -> explanation + unsupported + grounding_rate + provenance, error null
  * AI not available -> the SAVED real AMD report for this machine if one exists (provenance.provider "saved"),
                        otherwise explanation null + error (plain English) + fallback_summary (rule-based, no AI).
  * Never a made-up AI report.
"""
from __future__ import annotations

import copy
import json
import logging
import re
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import llm_client, prompts, verify
from .llm_client import LIVE_PROVIDERS, LLMClient, LLMError
from .prompts import get_field, to_plain, ts_text

log = logging.getLogger("forgeguard.reports")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_REPORTS_DIR = REPO_ROOT / "data" / "demo_reports"
SAVED_FORMAT = "forgeguard-saved-report-v1"
CACHE_SIZE = 200
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_CACHE: "OrderedDict[tuple[str, str], dict]" = OrderedDict()   # (run_id, machine_id) -> report
_AI_USED: "OrderedDict[str, set[str]]" = OrderedDict()          # run_id -> machines explained by live AI
_KEY_LOCKS: dict[tuple[str, str], threading.Lock] = {}
_STATE_LOCK = threading.Lock()


# --------------------------------------------------------------------------------------
# Report building
# --------------------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_report(machine_id: str) -> dict:
    return {"machine_id": machine_id, "explanation": None, "unsupported": [], "grounding_rate": None,
            "provenance": None, "error": None, "fallback_summary": None}


def error_report(case: Any, message: str) -> dict:
    """explanation null + plain error + rule-based summary built only from anomalies and notes."""
    case = to_plain(case) or {}
    report = empty_report(case.get("machine_id"))
    report["error"] = message
    report["fallback_summary"] = verify.fallback_summary(case)
    return report


def build_report(case: Any, explanation: dict, provenance: dict) -> dict:
    """Check every evidence ID against this case and return the frozen InspectionReport shape."""
    case = to_plain(case) or {}
    allowed = verify.allowed_evidence_ids(case)
    checked, unsupported, rate = verify.check_evidence(copy.deepcopy(explanation), allowed)
    checked["machine_id"] = case.get("machine_id")
    report = empty_report(case.get("machine_id"))
    report.update(explanation=checked, unsupported=unsupported, grounding_rate=rate, provenance=provenance)
    return report


def find_case(analysis: Any, machine_id: str) -> Any:
    for case in get_field(analysis, "cases") or []:
        if get_field(case, "machine_id") == machine_id:
            return case
    return None


# --------------------------------------------------------------------------------------
# In-memory cache (per run_id + machine_id) and the per-run AI limit (LLM_MAX_CASES)
# --------------------------------------------------------------------------------------
def _key_lock(key: tuple[str, str]) -> threading.Lock:
    with _STATE_LOCK:
        if key not in _KEY_LOCKS:
            if len(_KEY_LOCKS) > 4 * CACHE_SIZE:
                _KEY_LOCKS.clear()
            _KEY_LOCKS[key] = threading.Lock()
        return _KEY_LOCKS[key]


def _cache_get(key: tuple[str, str]) -> dict | None:
    with _STATE_LOCK:
        report = _CACHE.get(key)
        if report is None:
            return None
        _CACHE.move_to_end(key)
        report = copy.deepcopy(report)
    if report.get("provenance"):
        report["provenance"]["cached"] = True
    return report


def _cache_put(key: tuple[str, str], report: dict) -> None:
    with _STATE_LOCK:
        _CACHE[key] = copy.deepcopy(report)
        _CACHE.move_to_end(key)
        while len(_CACHE) > CACHE_SIZE:
            _CACHE.popitem(last=False)


def _ai_machines_used(run_id: str, machine_id: str) -> int:
    with _STATE_LOCK:
        return len(_AI_USED.get(run_id, set()) - {machine_id})


def _mark_ai_used(run_id: str, machine_id: str) -> None:
    with _STATE_LOCK:
        _AI_USED.setdefault(run_id, set()).add(machine_id)
        _AI_USED.move_to_end(run_id)
        while len(_AI_USED) > 100:
            _AI_USED.popitem(last=False)


def clear_cache() -> None:
    with _STATE_LOCK:
        _CACHE.clear()
        _AI_USED.clear()


# --------------------------------------------------------------------------------------
# Saved real AMD reports (data/demo_reports/<dataset>/<machine>.json)
# --------------------------------------------------------------------------------------
def case_signature(case: Any) -> list[list[Any]]:
    """Anomaly IDs + sensors + times. A saved report is used only if the case still matches."""
    case = to_plain(case) or {}
    rows = [[a.get("anomaly_id"), a.get("sensor"), ts_text(a.get("start")), ts_text(a.get("end"))]
            for a in case.get("anomalies") or []]
    return sorted(rows, key=lambda r: str(r[0]))


def saved_report_path(dataset_id: str, machine_id: str) -> Path | None:
    if not (_SAFE_NAME.match(str(dataset_id)) and _SAFE_NAME.match(str(machine_id))):
        return None
    return DEMO_REPORTS_DIR / str(dataset_id) / f"{machine_id}.json"


def save_report(dataset_id: str, case: Any, report: dict) -> Path:
    """Save one REAL AMD report (with provenance) for the demo. Mock / error reports are refused."""
    provenance = report.get("provenance") or {}
    if not report.get("explanation") or provenance.get("provider") != "amd_token_factory":
        raise ValueError("Only real AMD Token Factory reports (with an explanation) can be saved.")
    case_plain = to_plain(case) or {}
    path = saved_report_path(dataset_id, case_plain.get("machine_id"))
    if path is None:
        raise ValueError("dataset_id / machine_id may only contain letters, numbers, '_' and '-'.")
    data = {"format": SAVED_FORMAT, "dataset_id": dataset_id, "machine_id": case_plain.get("machine_id"),
            "saved_at": _now_iso(), "case_signature": case_signature(case_plain),
            "report": copy.deepcopy(report)}
    data["report"]["provenance"]["cached"] = False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_saved_report(dataset_id: str, case: Any) -> dict | None:
    """The saved AMD report for this case (provider 'saved', cached true), re-verified; None if missing/stale."""
    case_plain = to_plain(case) or {}
    path = saved_report_path(dataset_id, case_plain.get("machine_id"))
    if path is None or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.warning("Saved report %s cannot be read", path.name)
        return None
    if not isinstance(data, dict) or data.get("format") != SAVED_FORMAT:
        return None
    if data.get("case_signature") != case_signature(case_plain):
        log.warning("Saved report for %s/%s is stale (anomalies changed) - not used",
                    dataset_id, case_plain.get("machine_id"))
        return None
    saved = data.get("report") or {}
    explanation, provenance = saved.get("explanation"), dict(saved.get("provenance") or {})
    if not explanation or not provenance:
        return None
    provenance["provider"] = "saved"
    provenance["cached"] = True
    return build_report(case_plain, explanation, provenance)


# --------------------------------------------------------------------------------------
# Main entry point for POST /api/runs/{run_id}/explain/{machine_id}
# --------------------------------------------------------------------------------------
def explain_machine(analysis: Any, machine_id: str, client: LLMClient | None = None,
                    use_cache: bool = True) -> dict:
    """InspectionReport for one machine of one analysis run. Raises KeyError if the machine is not in the run.

    Call it from a normal `def` endpoint (not `async def`): it can wait up to about a minute for the AI.
    """
    case = find_case(analysis, machine_id)
    if case is None:
        raise KeyError(f"Machine '{machine_id}' is not in this analysis run.")
    run_id = str(get_field(analysis, "run_id") or "")
    key = (run_id, machine_id)
    with _key_lock(key):
        if use_cache:
            hit = _cache_get(key)
            if hit is not None:
                return hit
        report, cacheable = _explain_uncached(analysis, case, run_id, client)
        if cacheable:
            _cache_put(key, report)
        return report


def _explain_uncached(analysis: Any, case: Any, run_id: str,
                      client: LLMClient | None) -> tuple[dict, bool]:
    case_plain = to_plain(case) or {}
    machine_id = case_plain.get("machine_id")
    dataset = to_plain(get_field(analysis, "dataset")) or {}
    dataset_id = str(dataset.get("id") or "upload")

    if not case_plain.get("anomalies"):
        return error_report(case_plain, "No unusual readings for this machine, so no AI explanation was requested."), False

    client = client or llm_client.get_client()
    provider = client.provider

    if provider == "saved":
        saved = load_saved_report(dataset_id, case_plain)
        if saved:
            return saved, True
        return error_report(case_plain, "No saved AI report for this machine - showing the rule-based summary."), False

    if provider in LIVE_PROVIDERS and _ai_machines_used(run_id, machine_id) >= client.config.max_cases:
        saved = load_saved_report(dataset_id, case_plain)
        if saved:
            return saved, False
        return error_report(case_plain, f"AI limit for this analysis reached ({client.config.max_cases} machines, "
                                        "LLM_MAX_CASES). Run the analysis again to explain other machines."), False

    payload = prompts.build_case_payload(case_plain, readings=get_field(analysis, "readings"),
                                         sensors=get_field(analysis, "sensors"), dataset=dataset)
    messages = prompts.build_messages(payload)
    try:
        result = client.generate(messages, machine_id)
    except LLMError as exc:
        if provider in LIVE_PROVIDERS:
            saved = load_saved_report(dataset_id, case_plain)
            if saved:
                log.info("Live AI failed (%s) - serving the saved AMD report for %s", exc.kind, machine_id)
                return saved, False
        return error_report(case_plain, exc.message), False

    if provider in LIVE_PROVIDERS:
        _mark_ai_used(run_id, machine_id)
    provenance = {"provider": result.provider, "model": result.model, "hardware_label": client.hardware_label,
                  "latency_ms": result.latency_ms, "created_at": _now_iso(), "cached": False}
    return build_report(case_plain, result.explanation, provenance), True


# --------------------------------------------------------------------------------------
# GET /api/llm/status
# --------------------------------------------------------------------------------------
def llm_status(client: LLMClient | None = None) -> dict:
    """LLMStatus {provider, model, hardware_label, reachable, last_latency_ms, error} - never the key."""
    client = client or llm_client.get_client()
    status = client.status()
    if client.provider == "saved":
        files = sorted(DEMO_REPORTS_DIR.glob("*/*.json")) if DEMO_REPORTS_DIR.exists() else []
        status["reachable"] = bool(files)
        status["error"] = None if files else "No saved reports in data/demo_reports/ yet."
        if files:
            try:
                prov = json.loads(files[0].read_text(encoding="utf-8")).get("report", {}).get("provenance", {})
                status["model"] = prov.get("model") or status["model"]
                status["hardware_label"] = prov.get("hardware_label") or status["hardware_label"]
            except (OSError, ValueError, AttributeError):
                pass
    return status
