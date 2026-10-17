"""Save four genuine AMD Token Factory inspection reports for the ForgeGuard demo.

Run once from the repository root, with LLM_PROVIDER=amd_token_factory in
backend/.env. This script never prints or persists the API key.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

# Running "python scripts/save_demo_reports.py" otherwise puts only scripts/ on sys.path.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app import llm_client, reports
from backend.app.pipeline import ai_view, run_demo

TARGETS = (
    ("synthetic_fleet", "HP-01"),
    ("synthetic_fleet", "FP-02"),
    ("synthetic_fleet", "HP-02"),
    ("metropt3", "APU-01"),
)


def main() -> int:
    # Fail safely before making any paid inference requests.
    client = llm_client.get_client()
    if client.provider != "amd_token_factory":
        print("STOP: Set LLM_PROVIDER=amd_token_factory in backend/.env first.")
        return 1
    if not re.fullmatch(r"rc-[0-9a-fA-F]{48}", client.config.api_key):
        print("STOP: AMD key format is invalid. Check backend/.env privately.")
        return 1

    # Do not overwrite prior reports or repeat paid calls accidentally.
    existing = [str(path.relative_to(REPO_ROOT)) for ds, mid in TARGETS
                if (path := reports.saved_report_path(ds, mid)) is not None and path.exists()]
    if existing:
        print("STOP: Saved reports already exist. Do not rerun the four paid calls.")
        for path in existing:
            print("  ", path)
        return 1

    # Validate all cases before the first AMD request; AI must see linked notes only.
    prepared = {}
    try:
        for dataset_id in dict.fromkeys(ds for ds, _ in TARGETS):
            prepared[dataset_id] = ai_view(run_demo(dataset_id))
        for dataset_id, machine_id in TARGETS:
            result = prepared[dataset_id]
            case = next((c for c in result.cases if c.machine_id == machine_id), None)
            if case is None or not case.anomalies:
                print(f"STOP: {dataset_id}/{machine_id} is missing or has no anomalies.")
                return 1
    except Exception as exc:
        print(f"STOP: Dataset preparation failed: {type(exc).__name__}: {exc}")
        return 1

    print("ForgeGuard AI | Save REAL AMD demo reports")
    print(f"Configured provider: {client.provider} | model: {client.config.model}")
    print("dataset | machine | provider | model | latency_ms | grounding_rate | unsupported | saved")
    for index, (dataset_id, machine_id) in enumerate(TARGETS):
        if index:
            time.sleep(5)  # One AI request at a time; at least 5 seconds between.

        result = prepared[dataset_id]
        case = next(c for c in result.cases if c.machine_id == machine_id)
        print(f"[{index + 1}/4] Explaining {dataset_id}/{machine_id} ...", flush=True)
        try:
            report = reports.explain_machine(result, machine_id, client=client)
            provenance = report.get("provenance") or {}
            if report.get("error") or not report.get("explanation") or provenance.get("provider") != "amd_token_factory":
                print(f"STOP: {dataset_id}/{machine_id}: {report.get('error') or 'not a live AMD explanation'}")
                return 1
            path = reports.save_report(dataset_id, case, report)
        except Exception as exc:
            print(f"STOP: {dataset_id}/{machine_id}: {type(exc).__name__}: {exc}")
            return 1

        print(" | ".join((
            dataset_id, machine_id, str(provenance.get("provider")),
            str(provenance.get("model")), str(provenance.get("latency_ms")),
            str(report.get("grounding_rate")), str(len(report.get("unsupported") or [])), "yes",
        )), flush=True)
        print(f"  Saved to {path.relative_to(REPO_ROOT)}", flush=True)

    print("RESULT: PASS - 4 real AMD reports saved. Review the explanations before demo use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
