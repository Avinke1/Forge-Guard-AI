"""Test 4 (matching) - CLAUDE.md section 11 - plus note support and context notes."""

from datetime import datetime

from backend.app.matching import note_supports, relation
from backend.tests.conftest import case


def _linked(result, machine_id):
    return {l.note_id for a in case(result, machine_id).anomalies for l in a.linked_notes}


def test_hp01_linked_to_n13_n16(synthetic_run):
    assert {"N-13", "N-16"} <= _linked(synthetic_run.result, "HP-01")


def test_fp02_linked_to_n11_n12_with_relations(synthetic_run):
    r = synthetic_run.result
    assert {"N-11", "N-12"} <= _linked(r, "FP-02")
    (limit,) = [a for a in case(r, "FP-02").anomalies if a.method == "limit"]
    rel = {l.note_id: l.relation for l in limit.linked_notes}
    assert rel["N-11"] == "during" and rel["N-12"] == "after"


def test_hp02_linked_to_n19(synthetic_run):
    assert {"N-18", "N-19"} <= _linked(synthetic_run.result, "HP-02")


def test_notes_never_cross_machines(synthetic_run, metropt_run):
    for bundle in (synthetic_run, metropt_run):
        r = bundle.result
        note_machine = {n.note_id: n.machine_id for n in r.notes}
        for c in r.cases:
            assert all(n.machine_id == c.machine_id for n in c.notes)
            assert all(note_machine[nid] == c.machine_id for nid in _linked(r, c.machine_id))
            assert all(note_machine[nid] == c.machine_id for item in c.context for nid in item.note_ids)


def test_linked_notes_sorted_by_time(synthetic_run):
    times = {n.note_id: n.timestamp for n in synthetic_run.result.notes}
    for c in synthetic_run.result.cases:
        for a in c.anomalies:
            ts = [times[l.note_id] for l in a.linked_notes]
            assert ts == sorted(ts)


def test_unlinked_notes_stay_visible_on_machine(synthetic_run):
    fp01 = case(synthetic_run.result, "FP-01")
    assert [n.note_id for n in fp01.notes] == ["N-1", "N-7", "N-15"]
    assert not any(e.startswith("N-") for e in fp01.evidence_ids)


def test_context_notes_for_quality_warnings_and_ignored_spike(synthetic_run):
    r = synthetic_run.result
    ds01 = {c.kind: c.note_ids for c in case(r, "DS-01").context}
    assert ds01 == {"transient_ignored": ["N-10"]}
    ds02 = case(r, "DS-02").context
    assert next(c for c in ds02 if c.kind == "gap").note_ids == ["N-9"]
    assert next(c for c in ds02 if c.kind == "sensor_error").note_ids == ["N-14"]


def test_relation():
    s, e = datetime(2026, 10, 15, 14), datetime(2026, 10, 15, 16)
    assert relation(datetime(2026, 10, 15, 13), s, e) == "before"
    assert relation(datetime(2026, 10, 15, 14), s, e) == "during"
    assert relation(datetime(2026, 10, 15, 17), s, e) == "after"


def test_note_supports():
    assert note_supports("HP-02 high pressure alarm.", ("pressure", "relief valve"))
    assert note_supports("Operator reports HP-01 sounds louder than usual.", ("sound", "loud"))
    assert not note_supports("Start-of-week inspection on HP-01: no issues found.", ("bearing", "noise"))
    assert not note_supports("Die changed on FP-01 for a new part batch.", ("temperature", "oil"))
