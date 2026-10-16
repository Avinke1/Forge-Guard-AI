"""Generate ForgeGuard inspection reports with explicit provenance and fallbacks.

No API call is made unless generate() is invoked. No tests are generated here.
Team Lead: map your MachineCase/InspectionReport dataclasses in pipeline.py if needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

try:
    from .llm_client import AMDTokenFactoryClient, LLMError
    from .prompts import build_messages, build_repair_messages
    from .verify import as_mapping, collect_evidence_ids, parse_json_report, verify_report
except ImportError:
    from llm_client import AMDTokenFactoryClient, LLMError
    from prompts import build_messages, build_repair_messages
    from verify import as_mapping, collect_evidence_ids, parse_json_report, verify_report


REPORT_FIELDS = (
    "machine_id", "summary", "findings", "possible_causes",
    "recommended_checks", "missing_information", "uncertainty"
)


def _fallback(case: Any, reason: str) -> dict[str, Any]:
    """No fabricated LLM text; safe non-diagnostic summary from case counts only."""
    c = as_mapping(case)
    machine_id = str(c.get("machine_id", ""))
    anomalies = c.get("anomalies") or []
    amount = len(anomalies)
    text = (
        f"Rule-based summary: {amount} anomaly record(s) were supplied for "
        f"machine {machine_id}. An AI explanation is unavailable."
    )
    return {
        "case": c,
        "explanation": {
            "machine_id": machine_id,
            "summary": text,
            "findings": [],
            "possible_causes": [],
            "recommended_checks": [],
            "missing_information": ["An evidence-verified AI interpretation is not available."],
            "uncertainty": "No root cause or recommended intervention can be established from this fallback.",
        },
        "unsupported_claims": [],
        "grounding_rate": 0.0,
        "grounding_item_count": 0,
        "evidence_id_count": len(collect_evidence_ids(c)),
        "report_status": "rule_based_fallback",
        "error": reason,
        "provenance": {
            "provider": "none",
            "model": "none",
            "hardware_label": "AI unavailable; no AMD model response was produced",
            "latency_ms": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "cached": False,
        },
    }


class ReportGenerator:
    """Generate at most two completions: primary and one JSON repair."""

    def __init__(self, client: AMDTokenFactoryClient | None = None) -> None:
        self.client = client if client is not None else AMDTokenFactoryClient()

    def generate(self, case: Any) -> dict[str, Any]:
        c = as_mapping(case)
        if not c.get("machine_id"):
            raise ValueError("machine_id is required")
        if not collect_evidence_ids(c):
            return _fallback(c, "No source evidence IDs were available for this machine.")

        last_error = "Invalid model response"
        for repair_attempt in (False, True):
            try:
                messages = (build_repair_messages(c, "") if repair_attempt
                            else build_messages(c))
                completion = self.client.complete(messages)
                raw = parse_json_report(completion.content)
                result = verify_report(raw, c)
                if not result.schema_valid:
                    last_error = "Model JSON does not meet the ForgeGuard report schema: " + "; ".join(result.errors)
                    continue
                return {
                    "case": c,
                    "explanation": result.checked_report,
                    "unsupported_claims": result.unsupported_claims,
                    "grounding_rate": result.grounding_rate,
                    "grounding_item_count": result.total_items,
                    "evidence_id_count": len(collect_evidence_ids(c)),
                    "report_status": "verified_ids" if not result.unsupported_claims else "has_unsupported_claims",
                    "error": None,
                    "provenance": completion.provenance(),
                }
            except ValueError as exc:
                # Invalid JSON: attempt exactly one repair; never claim it was a verified report.
                last_error = str(exc)
            except LLMError as exc:
                # No further JSON repair when API is unavailable or unconfigured.
                return _fallback(c, str(exc))
        return _fallback(c, last_error)


def generate_inspection_report(case: Any, client: AMDTokenFactoryClient | None = None) -> dict[str, Any]:
    """Convenience entry point for Member 1's pipeline."""
    return ReportGenerator(client).generate(case)
