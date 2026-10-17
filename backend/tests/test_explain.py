"""Explain path as main.py wires it: ai_view() + Member 2's final reports.explain_machine (Member 1's checks).

Member 2's own tests (7-8) live in test_ai.py. Here only mock mode and a FAKE HTTP transport are used -
no request ever leaves the machine.
"""

import json

import pytest

from backend.app import llm_client, prompts, reports
from backend.app.llm_client import HTTPResponse, LLMClient, LLMConfig
from backend.app.pipeline import ai_view
from backend.app.schemas import InspectionReport
from backend.tests.conftest import case

AMD_MODEL = "self-dploy/DeepSeek-V4-Flash"  # what the real API returned in Member 2's smoke test


class FakeAMD:
    """Fake OpenAI-compatible server. `replies`: list of reply texts, or ints (= HTTP error status)."""

    def __init__(self, replies, fail_if_called=False):
        self.replies = list(replies)
        self.fail_if_called = fail_if_called
        self.posts = 0

    def __call__(self, method, url, headers, body, timeout):
        if self.fail_if_called:
            pytest.fail(f"network call attempted: {method} {url}")
        if method == "GET":
            return HTTPResponse(200, {}, json.dumps({"data": [{"id": "DeepSeek-V4-Flash"}]}).encode())
        self.posts += 1
        reply = self.replies.pop(0) if self.replies else 503
        if isinstance(reply, int):
            return HTTPResponse(reply, {}, b'{"error": {"message": "temporarily unavailable"}}')
        answer = {"id": "x", "model": AMD_MODEL,
                  "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}]}
        return HTTPResponse(200, {"content-type": "application/json"}, json.dumps(answer).encode())


def amd_client(fake, api_key="rc-test"):
    cfg = LLMConfig(provider="amd_token_factory", base_url="https://amd.example.test/v1", api_key=api_key)
    return LLMClient(cfg, transport=fake, sleep=lambda s: None)


def good_reply(machine_id, evidence, extra_cause_ids=()):
    return json.dumps({
        "machine_id": machine_id, "summary": "s",
        "findings": [{"statement": "f", "evidence": evidence}],
        "possible_causes": [{"cause": "c", "evidence": evidence + list(extra_cause_ids)}],
        "recommended_checks": [{"action": "a", "reason": "r", "evidence": evidence}],
        "missing_information": [], "uncertainty": "u",
    })


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    reports.clear_cache()
    monkeypatch.setattr(reports, "DEMO_REPORTS_DIR", tmp_path)  # never read or write data/demo_reports here
    yield
    reports.clear_cache()


@pytest.fixture
def view(synthetic_run):
    return ai_view(synthetic_run.result)


def payload_for(result, machine_id):
    v = ai_view(result)
    return prompts.build_case_payload(case(v, machine_id), readings=v.readings, sensors=v.sensors, dataset=v.dataset)


# ---------------------------------------------------------------- what the AI sees


def test_ai_payload_holds_only_evidence(synthetic_run):
    p = payload_for(synthetic_run.result, "HP-01")
    hp01 = case(synthetic_run.result, "HP-01")
    assert {n["note_id"] for n in p["notes"]} == {"N-13", "N-16"}  # N-3 (unlinked) is not sent
    assert 0 < len(p["key_readings"]) <= 12
    assert all(k["row_id"] in hp01.evidence_ids for k in p["key_readings"])
    assert any(k["vibration_mm_s"] == 8.0 for k in p["key_readings"])  # real sensor values
    assert {g["condition"] for g in p["general_guidance"]} == {"Vibration high", "Sound high"}
    assert all(g["guidance"] == "general guidance, not manufacturer-verified" for g in p["general_guidance"])


def test_metropt_payload_notes_and_guidance(metropt_run):
    p = payload_for(metropt_run.result, "APU-01")
    assert {n["note_id"] for n in p["notes"]} == {"N-5", "N-6"}  # not the Apr-Jun reports N-1..N-4
    assert [g["condition"] for g in p["general_guidance"]] == ["Air leak"]


def test_ai_view_keeps_all_notes_for_the_ui(synthetic_run):
    result = synthetic_run.result
    v = ai_view(result)
    assert "N-3" in {n.note_id for n in case(result, "HP-01").notes}  # API result unchanged
    assert {n.note_id for n in case(v, "HP-01").notes} == {"N-13", "N-16"}
    assert case(v, "FP-01").notes == [] and v.run_id == result.run_id


def test_label_never_in_payload(synthetic_run, metropt_run):
    for bundle in (synthetic_run, metropt_run):
        for c in bundle.result.cases:
            text = json.dumps(prompts.build_messages(payload_for(bundle.result, c.machine_id)))
            assert '"label"' not in text and "fault_events" not in text


# ---------------------------------------------------------------- AMD provider (fake transport)


def test_amd_success_becomes_inspection_report(view):
    a5 = next(a for a in case(view, "HP-01").anomalies if a.anomaly_id == "A-5")
    fake = FakeAMD([good_reply("HP-01", ["A-5", a5.row_ids[0]])])
    client = amd_client(fake)
    rep = InspectionReport.model_validate(reports.explain_machine(view, "HP-01", client=client))
    assert fake.posts == 1
    assert rep.error is None and rep.explanation.summary == "s"
    assert rep.provenance.provider == "amd_token_factory" and rep.provenance.model == AMD_MODEL
    assert rep.grounding_rate == 1.0 and rep.unsupported == []
    again = InspectionReport.model_validate(reports.explain_machine(view, "HP-01", client=client))
    assert again.provenance.cached is True and fake.posts == 1


def test_unlinked_note_id_is_unsupported(view):
    fake = FakeAMD([good_reply("HP-01", ["A-5"], extra_cause_ids=["N-3"])])  # N-3 is not linked evidence
    rep = InspectionReport.model_validate(reports.explain_machine(view, "HP-01", client=amd_client(fake)))
    assert [(u.section, u.index) for u in rep.unsupported] == [("possible_causes", 0)]
    assert rep.grounding_rate == pytest.approx(0.667)


def test_invalid_json_one_repair_then_fallback(view):
    fake = FakeAMD(["not json", "still not json"])
    rep = InspectionReport.model_validate(reports.explain_machine(view, "HP-01", client=amd_client(fake)))
    assert fake.posts == 2
    assert rep.explanation is None and rep.provenance is None and rep.grounding_rate is None
    assert rep.error and rep.fallback_summary.startswith("Rule-based summary (no AI)")


def test_invalid_then_repaired(view):
    fake = FakeAMD(["oops", good_reply("HP-01", ["A-5"])])
    rep = reports.explain_machine(view, "HP-01", client=amd_client(fake))
    assert fake.posts == 2 and rep["explanation"] is not None


def test_fallback_summary_lists_only_linked_notes(view):
    rep = reports.explain_machine(view, "FP-02", client=amd_client(FakeAMD([503, 503])))
    text = rep["fallback_summary"]
    assert text.startswith("Rule-based summary (no AI): FP-02 - priority")
    assert "A-2" in text and "N-11" in text
    assert "N-2 " not in text  # FP-02's unlinked start-of-week note


def test_amd_down_uses_saved_report(view):
    good = reports.explain_machine(view, "HP-01", client=amd_client(FakeAMD([good_reply("HP-01", ["A-5"])])),
                                   use_cache=False)
    reports.save_report("synthetic_fleet", case(view, "HP-01"), good)
    reports.clear_cache()
    rep = InspectionReport.model_validate(reports.explain_machine(view, "HP-01", client=amd_client(FakeAMD([503, 503]))))
    assert rep.provenance.provider == "saved" and rep.provenance.cached is True
    assert rep.provenance.model == AMD_MODEL and rep.explanation.summary == "s"


def test_missing_key_never_calls_network(view):
    client = amd_client(FakeAMD([], fail_if_called=True), api_key="")
    rep = InspectionReport.model_validate(reports.explain_machine(view, "HP-01", client=client))
    assert rep.explanation is None and "key missing" in rep.error
    status = reports.llm_status(client)
    assert status["provider"] == "amd_token_factory" and status["reachable"] is False


def test_no_ai_call_without_anomalies(view):
    fake = FakeAMD([], fail_if_called=True)
    rep = InspectionReport.model_validate(reports.explain_machine(view, "FP-01", client=amd_client(fake)))
    assert rep.explanation is None and rep.fallback_summary.startswith("Rule-based summary (no AI)")


def test_unknown_machine_raises_keyerror(view):
    with pytest.raises(KeyError):
        reports.explain_machine(view, "XX-99", client=amd_client(FakeAMD([], fail_if_called=True)))


def test_mock_client_is_default_in_tests():
    llm_client.set_client(None)
    assert llm_client.get_client().provider == "mock"


def test_empty_findings_trigger_one_repair(view):
    empty = json.loads(good_reply("HP-01", ["A-5"]))
    empty["findings"] = []
    fake = FakeAMD([json.dumps(empty), good_reply("HP-01", ["A-5"])])
    rep = reports.explain_machine(view, "HP-01", client=amd_client(fake))
    assert fake.posts == 2 and rep["explanation"]["findings"]
