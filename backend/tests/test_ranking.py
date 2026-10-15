"""Test 5 (ranking) and test 10 (label never in a case) - CLAUDE.md section 11 - plus pipeline errors."""

from datetime import datetime

import pytest

from backend.app.datasets import load_demo_frames
from backend.app.pipeline import AnalysisError, analyze
from backend.app.ranking import anomaly_severity, machine_score, priority, queue_key
from backend.tests.conftest import case, frame


# ---------------------------------------------------------------- test 5: planted priorities


def test_queue_order_and_priorities(synthetic_run):
    r = synthetic_run.result
    prio = {c.machine_id: c.priority for c in r.cases}
    assert r.cases[0].machine_id == "HP-01" and prio["HP-01"] == "HIGH"
    assert prio["FP-02"] in ("HIGH", "MEDIUM")
    assert prio["HP-02"] in ("MEDIUM", "HIGH")
    assert prio["DS-01"] == "OK" and prio["FP-01"] == "OK"
    assert prio["DS-02"] in ("LOW", "OK")  # data-quality warnings only, never HIGH
    scores = [c.score for c in r.cases]
    assert scores == sorted(scores, reverse=True)


def test_metropt_case_flagged(metropt_run):
    assert case(metropt_run.result, "APU-01").priority in ("HIGH", "MEDIUM")


def test_severity_formula():
    assert anomaly_severity("limit", 0.10, 4, False) == 1.0
    assert anomaly_severity("limit", 0.05, 2, False) == 0.5  # 0.6*0.5 + 0.4*0.5
    assert anomaly_severity("limit", 0.05, 2, True) == 0.6
    assert anomaly_severity("zscore", 3.0, 1, False) == 0.4  # 0.6*0.5 + 0.4*0.25
    assert anomaly_severity("zscore", 60.0, 100, True) == 1.0  # clamped


def test_machine_score_and_priority():
    assert machine_score({}) == 0.0
    assert machine_score({"a": 0.5}) == 0.5
    assert machine_score({"a": 0.5, "b": 0.2}) == 0.55
    assert machine_score({"a": 0.5, "b": 0.2, "c": 0.1, "d": 0.1}) == 0.6  # bonus capped at 0.1
    assert priority(0.7, True, False) == "HIGH"
    assert priority(0.4, True, False) == "MEDIUM"
    assert priority(0.1, True, False) == "LOW"
    assert priority(0.0, False, True) == "LOW"
    assert priority(0.0, False, False) == "OK"


def test_ties_earlier_start_first():
    early = queue_key(0.5, datetime(2026, 10, 14, 8), "MEDIUM", "ZZ-99")
    late = queue_key(0.5, datetime(2026, 10, 14, 9), "MEDIUM", "AA-01")
    assert sorted([late, early]) == [early, late]


def test_evidence_ids_only_case_ids(synthetic_run):
    for c in synthetic_run.result.cases:
        allowed = {a.anomaly_id for a in c.anomalies} | {r for a in c.anomalies for r in a.row_ids} | {
            l.note_id for a in c.anomalies for l in a.linked_notes
        }
        assert set(c.evidence_ids) == allowed


# ---------------------------------------------------------------- test 10: label never in a case


def test_label_never_in_result(synthetic_run, metropt_run):
    for bundle in (synthetic_run, metropt_run):
        r = bundle.result
        assert all("label" not in reading.model_dump() for reading in r.readings)
        for c in r.cases:
            assert '"label"' not in c.model_dump_json()
        assert "label" not in bundle.validation.readings.columns


def test_label_values_do_not_change_results():
    readings, notes = load_demo_frames("synthetic_fleet")
    flipped = readings.copy()
    flipped["label"] = flipped["label"].map({"0": "1", "1": "0"})
    a = analyze(readings, notes, "synthetic_fleet", run_id="x").result
    b = analyze(flipped, notes, "synthetic_fleet", run_id="x").result
    assert a.model_dump_json() == b.model_dump_json()


# ---------------------------------------------------------------- pipeline errors


def test_pipeline_raises_plain_error_without_machine_id():
    with pytest.raises(AnalysisError, match="machine_id"):
        analyze(frame("timestamp,rpm\n2026-10-14T00:00:00,1200\n"), None, "synthetic_fleet")


def test_demo_result_shape(synthetic_run):
    r = synthetic_run.result
    assert r.dataset.id == "synthetic_fleet" and r.dataset.synthetic
    assert r.dataset.attribution == "SYNTHETIC demo data - not real plant measurements"
    assert set(r.sensors) == {"vibration_mm_s", "temperature_c", "pressure_bar", "sound_db", "rpm"}
    assert len(r.readings) == 1724 and len(r.cases) == 6
    ds02_r1613 = next(x for x in r.readings if x.row_id == "R1613")
    assert ds02_r1613.model_dump()["rpm"] is None
