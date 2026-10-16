"""run_analysis: 1 Validate -> 2 Detect -> 3 Match notes -> 4 Rank -> AnalysisResult.

Steps 5-6 (explain + verify) run later, on demand per machine (POST /api/runs/{run_id}/explain/{machine_id}).
The "label" column is removed in step 1, so it can never reach a case, the ranking or an LLM prompt.
"""

import uuid
from dataclasses import dataclass

import pandas as pd

from backend.app.datasets import DatasetConfig, get_dataset, load_demo_frames
from backend.app.detection import Detected, DetectionOutput, detect
from backend.app.matching import MatchOutput, match
from backend.app.ranking import QUALITY_KINDS, anomaly_severity, machine_score, priority, queue_key
from backend.app.schemas import (
    AnalysisResult,
    Anomaly,
    LinkedNote,
    MachineCase,
    Note,
    Reading,
    ValidationReport,
)
from backend.app.validation import ValidationOutput, validate


class AnalysisError(ValueError):
    """Validation found errors, so the analysis stops. The message is plain English for the user."""

    def __init__(self, report: ValidationReport):
        self.report = report
        super().__init__(" ".join(report.errors) or "The readings file could not be analysed.")


@dataclass
class AnalysisBundle:
    """The API result plus the internal pieces (used by scripts/evaluate.py and the explain step)."""

    result: AnalysisResult
    validation: ValidationOutput
    detection: DetectionOutput
    matches: MatchOutput


def _readings_models(df: pd.DataFrame, sensors: list[str]) -> list[Reading]:
    out: list[Reading] = []
    values = df[sensors].astype(object).where(df[sensors].notna(), None)
    for rid, ts, mid, vals in zip(df["row_id"], df["timestamp"], df["machine_id"], values.itertuples(index=False)):
        extra = {name: (None if v is None else float(v)) for name, v in zip(sensors, vals)}
        out.append(Reading(row_id=str(rid), timestamp=ts.to_pydatetime(), machine_id=str(mid), **extra))
    return out


def _note_models(notes: pd.DataFrame) -> list[Note]:
    return [
        Note(
            note_id=str(r.note_id),
            machine_id=str(r.machine_id),
            timestamp=pd.Timestamp(r.timestamp).to_pydatetime(),
            text=str(r.text),
            source=str(r.source),
            synthetic=bool(r.synthetic),
        )
        for r in notes.itertuples(index=False)
    ]


def _anomaly_model(a: Detected, severity: float, matches: MatchOutput) -> Anomaly:
    return Anomaly(
        anomaly_id=a.anomaly_id,
        machine_id=a.machine_id,
        sensor=a.sensor,
        start=pd.Timestamp(a.start).to_pydatetime(),
        end=pd.Timestamp(a.end).to_pydatetime(),
        peak=float(a.peak),
        unit=a.unit,
        method=a.method,
        reason=a.reason,
        row_ids=list(a.row_ids),
        severity=severity,
        linked_notes=[LinkedNote(note_id=l.note_id, relation=l.relation) for l in matches.links.get(a.anomaly_id, [])],
    )


def _build_cases(
    machine_ids: list[str], anomalies: list[Detected], notes: list[Note], matches: MatchOutput
) -> list[MachineCase]:
    cases: list[tuple[tuple, MachineCase]] = []
    for mid in machine_ids:
        mine = [a for a in anomalies if a.machine_id == mid]
        models: list[Anomaly] = []
        by_sensor: dict[str, float] = {}
        for a in mine:
            supported = any(l.supports for l in matches.links.get(a.anomaly_id, []))
            sev = anomaly_severity(a.method, a.magnitude_ratio, a.duration_hours, supported)
            by_sensor[a.sensor] = max(sev, by_sensor.get(a.sensor, 0.0))
            models.append(_anomaly_model(a, sev, matches))
        context = matches.context.get(mid, [])
        score = machine_score(by_sensor)
        prio = priority(score, bool(models), any(c.kind in QUALITY_KINDS for c in context))

        evidence: list[str] = []
        for m in models:
            evidence.append(m.anomaly_id)
            evidence.extend(m.row_ids)
        for m in models:
            evidence.extend(l.note_id for l in m.linked_notes)
        evidence = list(dict.fromkeys(evidence))

        case = MachineCase(
            machine_id=mid,
            priority=prio,
            score=score,
            anomalies=models,
            notes=sorted([n for n in notes if n.machine_id == mid], key=lambda n: (n.timestamp, n.note_id)),
            evidence_ids=evidence,
            context=context,
        )
        first_start = min((m.start for m in models), default=None)
        cases.append((queue_key(score, first_start, prio, mid), case))
    return [c for _, c in sorted(cases, key=lambda kc: kc[0])]


def analyze(
    readings_raw: pd.DataFrame,
    notes_raw: pd.DataFrame | None,
    dataset: str | DatasetConfig,
    run_id: str | None = None,
    include_readings: bool = True,
) -> AnalysisBundle:
    ds = get_dataset(dataset) if isinstance(dataset, str) else dataset
    v = validate(readings_raw, notes_raw, ds)
    if not v.report.ok:
        raise AnalysisError(v.report)

    det = detect(v.readings, ds)
    for i, a in enumerate(det.anomalies, start=1):
        a.anomaly_id = f"A-{i}"
    matches = match(det.anomalies, det.transients, v.quality_events, v.notes, ds)

    sensors = [c for c in ds.sensors if c in v.readings.columns]
    notes = _note_models(v.notes)
    machine_ids = sorted(str(m) for m in v.readings["machine_id"].unique())
    result = AnalysisResult(
        run_id=run_id or uuid.uuid4().hex[:12],
        dataset=ds.ref(),
        validation=v.report,
        sensors={name: ds.sensors[name].info() for name in sensors},
        readings=_readings_models(v.readings, sensors) if include_readings else [],
        notes=notes,
        cases=_build_cases(machine_ids, det.anomalies, notes, matches),
    )
    return AnalysisBundle(result=result, validation=v, detection=det, matches=matches)


def run_analysis(readings_df: pd.DataFrame, notes_df: pd.DataFrame | None, dataset_id: str) -> AnalysisResult:
    return analyze(readings_df, notes_df, dataset_id).result


def run_demo(dataset_id: str) -> AnalysisResult:
    readings, notes = load_demo_frames(dataset_id)
    return run_analysis(readings, notes, dataset_id)


def ai_view(result: AnalysisResult) -> AnalysisResult:
    """The run as the AI sees it: each case keeps only the notes LINKED to its anomalies.

    MachineCase.notes holds every note of the machine (unlinked ones are background for the UI).
    reports.py treats case.notes as evidence, so unlinked notes must not reach it: they would be sent
    to the AI as citable evidence and listed in the rule-based fallback summary.
    RULE: everything that calls reports.explain_machine or reports.save_report passes ai_view(result) -
    main.py and every script (e.g. scripts/save_demo_reports.py). The API response itself keeps all notes.
    """
    cases = []
    for case in result.cases:
        linked = {link.note_id for a in case.anomalies for link in a.linked_notes}
        cases.append(case.model_copy(update={"notes": [n for n in case.notes if n.note_id in linked]}))
    return result.model_copy(update={"cases": cases})
