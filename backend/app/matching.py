"""Step 3 - MATCH NOTES (CLAUDE.md section 5.3).

Same machine_id only (exact match, no fuzzy joins). A note is linked to an anomaly when its timestamp is
inside [start - 24 h, end + 24 h]; relation = "before" | "during" | "after".
A linked note SUPPORTS the anomaly (ranking +0.1) when its text names the same symptom (sensor keywords,
matched at a word start) and does not say that everything was fine.
CONTEXT (STEP 2 decision 4): a note within +-2 h of a data-quality warning or an ignored one-off spike is
attached to that context item. Context is shown on the machine page, never used as evidence.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd

from backend.app.datasets import DatasetConfig
from backend.app.detection import Detected, Transient
from backend.app.schemas import ContextItem
from backend.app.validation import QualityEvent

NOTE_WINDOW = timedelta(hours=24)
CONTEXT_WINDOW = timedelta(hours=2)
ALL_CLEAR_PHRASES = ("no issues", "no issue", "all readings normal", "all tight", "no problem")


@dataclass
class NoteLink:
    note_id: str
    relation: str  # before | during | after
    supports: bool


@dataclass
class MatchOutput:
    links: dict[str, list[NoteLink]] = field(default_factory=dict)  # anomaly_id -> links, sorted by note time
    context: dict[str, list[ContextItem]] = field(default_factory=dict)  # machine_id -> items, sorted by time


def relation(note_time: datetime, start: datetime, end: datetime) -> str:
    if note_time < start:
        return "before"
    if note_time > end:
        return "after"
    return "during"


def note_supports(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    if any(phrase in lowered for phrase in ALL_CLEAR_PHRASES):
        return False
    return any(re.search(r"\b" + re.escape(k.lower()), lowered) for k in keywords)


def _notes_near(notes: pd.DataFrame, machine_id: str, start: datetime, end: datetime, window: timedelta) -> pd.DataFrame:
    if notes.empty:
        return notes
    same = notes[notes["machine_id"] == machine_id]
    return same[(same["timestamp"] >= start - window) & (same["timestamp"] <= end + window)].sort_values(
        ["timestamp", "note_id"], kind="stable"
    )


def link_notes(anomalies: list[Detected], notes: pd.DataFrame, ds: DatasetConfig) -> dict[str, list[NoteLink]]:
    links: dict[str, list[NoteLink]] = {}
    for a in anomalies:
        keywords = ds.sensors[a.sensor].keywords
        near = _notes_near(notes, a.machine_id, a.start, a.end, NOTE_WINDOW)
        links[a.anomaly_id] = [
            NoteLink(
                note_id=str(row.note_id),
                relation=relation(row.timestamp, a.start, a.end),
                supports=note_supports(str(row.text), keywords),
            )
            for row in near.itertuples(index=False)
        ]
    return links


def build_context(
    quality_events: list[QualityEvent], transients: list[Transient], notes: pd.DataFrame
) -> dict[str, list[ContextItem]]:
    context: dict[str, list[ContextItem]] = {}
    items: list[tuple[str, ContextItem]] = []
    for e in quality_events:
        items.append(
            (e.machine_id, ContextItem(kind=e.kind, message=e.message, start=e.start, end=e.end, sensor=e.sensor,
                                       row_ids=list(e.row_ids)))
        )
    for t in transients:
        items.append(
            (t.machine_id, ContextItem(kind="transient_ignored", message=t.message, start=t.start, end=t.end,
                                       sensor=t.sensor, row_ids=list(t.row_ids)))
        )
    for machine_id, item in items:
        if item.start is not None:
            near = _notes_near(notes, machine_id, item.start, item.end or item.start, CONTEXT_WINDOW)
            item.note_ids = [str(n) for n in near["note_id"]] if not near.empty else []
        context.setdefault(machine_id, []).append(item)
    for machine_id in context:
        context[machine_id].sort(key=lambda c: (c.start or datetime.max, c.kind))
    return context


def match(
    anomalies: list[Detected],
    transients: list[Transient],
    quality_events: list[QualityEvent],
    notes: pd.DataFrame,
    ds: DatasetConfig,
) -> MatchOutput:
    return MatchOutput(
        links=link_notes(anomalies, notes, ds),
        context=build_context(quality_events, transients, notes),
    )
