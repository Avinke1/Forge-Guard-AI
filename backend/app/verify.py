"""Strict ForgeGuard report-schema and evidence-reference verification.

A valid evidence ID proves only that a referenced item exists in THIS machine case.
It is NOT proof that the cited item logically supports the model's statement.
No ML ground-truth labels enter the verification process.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Mapping

REPORT_KEYS = frozenset({
    "machine_id", "summary", "findings", "possible_causes",
    "recommended_checks", "missing_information", "uncertainty",
})
ITEM_KEYS = {
    "findings": frozenset({"statement", "evidence"}),
    "possible_causes": frozenset({"cause", "evidence"}),
    "recommended_checks": frozenset({"action", "reason", "evidence"}),
}
EVIDENCE_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


def as_mapping(value: Any) -> dict[str, Any]:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dict__"):
        return vars(value).copy()
    raise TypeError("Expected a dict or object with fields")


def _records(value: Any) -> list[Any]:
    return value if isinstance(value, list) else list(value) if isinstance(value, tuple) else []


def collect_evidence_ids(case: Any) -> set[str]:
    """Collect only actual anomaly, reading and note IDs for the selected machine."""
    obj = as_mapping(case)
    machine_id = str(obj.get("machine_id", ""))
    found: set[str] = set()

    def put(value: Any) -> None:
        if isinstance(value, str) and EVIDENCE_ID_PATTERN.fullmatch(value):
            found.add(value)

    for record in _records(obj.get("anomalies")):
        r = as_mapping(record)
        if r.get("machine_id") not in (None, "", machine_id):
            continue
        put(r.get("anomaly_id"))
        for rid in _records(r.get("row_ids")):
            put(rid)

    for record in _records(obj.get("notes")):
        r = as_mapping(record)
        if r.get("machine_id") not in (None, "", machine_id):
            continue
        put(r.get("note_id"))

    for record in _records(obj.get("readings")):
        r = as_mapping(record)
        if r.get("machine_id") not in (None, "", machine_id):
            continue
        put(r.get("row_id"))

    # Do NOT trust case.evidence_ids without a corresponding data record.
    return found


def parse_json_report(text: str) -> dict[str, Any]:
    """Parse one JSON object; tolerate only an outer Markdown JSON fence."""
    value = text.strip()
    if value.startswith("```") and value.endswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value)
    try:
        data = json.loads(value)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("Model output is not valid JSON.") from exc
    if not isinstance(data, dict):
        raise ValueError("Model output must be one JSON object.")
    return data


@dataclass
class Verification:
    schema_valid: bool
    errors: list[str]
    checked_report: dict[str, Any] | None
    unsupported_claims: list[dict[str, Any]]
    grounding_rate: float
    total_items: int
    supported_items: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_report(report: Mapping[str, Any], case: Any) -> Verification:
    """Check exact report shape and mark ungrounded items, never erase them silently."""
    case_data = as_mapping(case)
    expected_machine = str(case_data.get("machine_id", ""))
    errors: list[str] = []

    if set(report) != REPORT_KEYS:
        errors.append(f"Report fields differ from contract: expected {sorted(REPORT_KEYS)}")
    if not expected_machine or report.get("machine_id") != expected_machine:
        errors.append("Report machine_id does not match the case.")
    for field in ("summary", "uncertainty"):
        if not isinstance(report.get(field), str) or not report.get(field, "").strip():
            errors.append(f"{field} must be non-empty text.")
    missing = report.get("missing_information")
    if not isinstance(missing, list) or any(not isinstance(x, str) for x in missing):
        errors.append("missing_information must be a list of strings.")

    for field, wanted in ITEM_KEYS.items():
        items = report.get(field)
        if not isinstance(items, list):
            errors.append(f"{field} must be a list.")
            continue
        if len(items) > 30:
            errors.append(f"{field} contains too many entries (max 30).")
        for index, item in enumerate(items):
            if not isinstance(item, dict) or set(item) != wanted:
                errors.append(f"{field}[{index}] has incorrect fields.")
                continue
            for text_field in wanted - {"evidence"}:
                if not isinstance(item[text_field], str) or not item[text_field].strip():
                    errors.append(f"{field}[{index}].{text_field} must be non-empty text.")
            if not isinstance(item.get("evidence"), list) or any(
                not isinstance(eid, str) for eid in item["evidence"]
            ):
                errors.append(f"{field}[{index}].evidence must be a list of ID strings.")

    if errors:
        return Verification(False, errors, None, [], 0.0, 0, 0)

    allowed_ids = collect_evidence_ids(case_data)
    checked = dict(report)
    unsupported: list[dict[str, Any]] = []
    total = supported = 0
    for field in ITEM_KEYS:
        result_items: list[dict[str, Any]] = []
        for index, item in enumerate(report[field]):
            total += 1
            referenced = item["evidence"]
            valid_ids = list(dict.fromkeys(eid for eid in referenced if eid in allowed_ids))
            invalid_ids = list(dict.fromkeys(eid for eid in referenced if eid not in allowed_ids))
            # Fail closed on any invented ID; empty evidence is also unsupported.
            ok = bool(valid_ids) and not invalid_ids
            supported += int(ok)
            enriched = {
                **item,
                "supported": ok,
                "verified_evidence_ids": valid_ids,
                "invalid_evidence_ids": invalid_ids,
            }
            result_items.append(enriched)
            if not ok:
                unsupported.append({
                    "section": field,
                    "index": index,
                    "text": item.get("statement") or item.get("cause") or item.get("action"),
                    "invalid_evidence_ids": invalid_ids,
                    "reason": "No valid evidence" if not valid_ids else "Contains unknown evidence IDs",
                })
        checked[field] = result_items

    return Verification(
        schema_valid=True,
        errors=[],
        checked_report=checked,
        unsupported_claims=unsupported,
        grounding_rate=round(supported / total, 4) if total else 0.0,
        total_items=total,
        supported_items=supported,
    )
