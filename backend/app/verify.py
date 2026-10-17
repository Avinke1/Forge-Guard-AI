"""ForgeGuard AI - step 6: check the AI output before anyone sees it.

  parse_explanation()      AI reply text -> clean explanation dict (or a problem message)
  allowed_evidence_ids()   IDs that really exist in this machine case (anomalies, their rows, notes)
  check_evidence()         every item must cite >= 1 ID and ONLY allowed IDs -> unsupported + grounding_rate
  fallback_summary()       "Rule-based summary (no AI): ..." built only from anomalies + notes

Note: a valid ID proves the evidence EXISTS in this case. It does not prove the AI's sentence
is correct - the technician still reads the evidence. Unsupported items are never deleted,
they are listed in "unsupported" so the UI can mark them.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .prompts import short_time, to_plain

SECTIONS = ("findings", "possible_causes", "recommended_checks")
TEXT_KEY = {"findings": "statement", "possible_causes": "cause", "recommended_checks": "action"}
REQUIRED_KEYS = ("summary", "findings", "possible_causes", "recommended_checks")
MAX_ITEMS_PER_SECTION = 10
MAX_TEXT = 1000

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
_ID_SPLIT = re.compile(r"[,;\s]+")


# --------------------------------------------------------------------------------------
# Evidence IDs
# --------------------------------------------------------------------------------------
def normalize_id(value: Any) -> str:
    """'a-1' -> 'A-1', 'R-412' / 'r412' -> 'R412', 'n13' -> 'N-13'. Other text is returned trimmed."""
    text = str(value).strip().strip("[](){}'\"`.,;:").upper().replace(" ", "")
    m = re.fullmatch(r"R-?(\d+)", text)
    if m:
        return f"R{int(m.group(1))}"
    m = re.fullmatch(r"([AN])-?(\d+)", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2))}"
    return text


def allowed_evidence_ids(case: Any) -> set[str]:
    """Anomaly IDs + all their reading row IDs + matched note IDs of THIS case."""
    case = to_plain(case) or {}
    allowed: set[str] = set()
    for a in case.get("anomalies") or []:
        if a.get("anomaly_id"):
            allowed.add(normalize_id(a["anomaly_id"]))
        for rid in a.get("row_ids") or []:
            allowed.add(normalize_id(rid))
    for n in case.get("notes") or []:
        if n.get("note_id"):
            allowed.add(normalize_id(n["note_id"]))
    allowed.discard("")
    return allowed


# --------------------------------------------------------------------------------------
# Parse the AI reply
# --------------------------------------------------------------------------------------
def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = " ".join(str(v) for v in value)
    return str(value).strip()[:MAX_TEXT]


def _evidence(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = _ID_SPLIT.split(value)
    elif isinstance(value, (list, tuple)):
        parts = [str(v) for v in value]
    else:
        parts = [str(value)]
    out: list[str] = []
    for p in parts:
        nid = normalize_id(p)
        if nid and nid not in out:
            out.append(nid)
    return out


def _items(value: Any, section: str) -> list[dict] | None:
    """Clean one section. None means 'not a list' (a format problem)."""
    if value is None:
        return []
    if not isinstance(value, list):
        return None
    key = TEXT_KEY[section]
    out = []
    for item in value[:MAX_ITEMS_PER_SECTION]:
        if isinstance(item, dict):
            text = _text(item.get(key) or item.get("text") or item.get("description"))
            ev = _evidence(item.get("evidence", item.get("evidence_ids")))
            reason = _text(item.get("reason"))
        else:                                   # a plain string: keep it, it will be unsupported
            text, ev, reason = _text(item), [], ""
        clean = {key: text, "reason": reason, "evidence": ev} if section == "recommended_checks" \
            else {key: text, "evidence": ev}
        if clean[key]:
            out.append(clean)
    return out


def parse_explanation(text: str | None, machine_id: str) -> tuple[dict | None, str | None]:
    """AI reply -> (explanation, None) or (None, 'what is wrong').

    Tolerant on purpose (each retry costs the team's shared AMD limit): it accepts a code fence
    or a short line before the JSON, ignores extra keys, and sets machine_id to the real case.
    """
    if not text or not text.strip():
        return None, "the reply was empty"
    body = _FENCE.sub("", text.strip())
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None, "no JSON object was found"
    try:
        data = json.loads(body[start:end + 1])
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON ({exc.msg} at character {exc.pos})"
    if not isinstance(data, dict):
        return None, "the JSON is not one object"
    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        return None, "missing keys: " + ", ".join(missing)

    explanation: dict[str, Any] = {"machine_id": machine_id, "summary": _text(data.get("summary"))}
    for section in SECTIONS:
        items = _items(data.get(section), section)
        if items is None:
            return None, f"'{section}' must be a list"
        explanation[section] = items
    info = data.get("missing_information")
    if isinstance(info, str):
        info = [info]
    explanation["missing_information"] = [_text(x) for x in (info or []) if _text(x)][:MAX_ITEMS_PER_SECTION]
    explanation["uncertainty"] = _text(data.get("uncertainty"))

    if not explanation["summary"]:
        return None, "the summary is empty"
    if not explanation["findings"]:          # explain is only called for machines WITH anomalies
        return None, "findings is empty - give 1-4 findings, each citing the anomaly IDs it describes"
    return explanation, None


# --------------------------------------------------------------------------------------
# Evidence check + grounding rate
# --------------------------------------------------------------------------------------
def check_evidence(explanation: dict, allowed: set[str]) -> tuple[dict, list[dict], float | None]:
    """Returns (explanation with normalized IDs, unsupported [{section, index}], grounding_rate).

    An item is supported only if it cites at least one ID and EVERY cited ID exists in this case.
    grounding_rate = supported items / all items (findings + possible_causes + recommended_checks),
    or None when there are no items to check.
    """
    explanation = to_plain(explanation) or {}
    unsupported: list[dict] = []
    total = supported = 0
    for section in SECTIONS:
        items = explanation.get(section) or []
        for index, item in enumerate(items):
            ev = _evidence(item.get("evidence"))
            item["evidence"] = ev
            total += 1
            if ev and all(e in allowed for e in ev):
                supported += 1
            else:
                unsupported.append({"section": section, "index": index})
        explanation[section] = items
    rate = round(supported / total, 3) if total else None
    return explanation, unsupported, rate


# --------------------------------------------------------------------------------------
# Rule-based fallback (no AI)
# --------------------------------------------------------------------------------------
def _clip(text: Any, n: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 3].rstrip() + "..."


def fallback_summary(case: Any, max_anomalies: int = 5, max_notes: int = 4) -> str:
    """Plain text built ONLY from the case's anomalies and notes - never from an AI."""
    case = to_plain(case) or {}
    machine = case.get("machine_id") or "This machine"
    priority = case.get("priority") or "?"
    score = case.get("score")
    head = f"Rule-based summary (no AI): {machine} - priority {priority}"
    if isinstance(score, (int, float)):
        head += f" (score {score:.2f})"
    head += "."

    anomalies = sorted(case.get("anomalies") or [], key=lambda a: -(a.get("severity") or 0))
    if not anomalies:
        tail = " No unusual readings were found."
        if priority == "LOW":
            tail += " Only data-quality warnings - see the validation report."
        return head + tail

    parts = []
    for a in anomalies[:max_anomalies]:
        when = f"{short_time(a.get('start'))} to {short_time(a.get('end'))}"
        parts.append(f"{a.get('anomaly_id')} {a.get('sensor')} ({when}): {_clip(a.get('reason'), 160)}")
    text = f"{head} {len(anomalies)} unusual reading pattern(s): " + "; ".join(parts)
    if len(anomalies) > max_anomalies:
        text += f"; plus {len(anomalies) - max_anomalies} more"
    text += "."

    notes = sorted(case.get("notes") or [], key=lambda n: str(n.get("timestamp")))
    if notes:
        note_parts = [f"{n.get('note_id')} ({short_time(n.get('timestamp'))}, {n.get('source')}): "
                      f"\"{_clip(n.get('text'), 140)}\"" for n in notes[:max_notes]]
        text += " Related notes: " + "; ".join(note_parts) + "."
    text += " A technician should check this evidence before acting."
    return text
