"""explain.py adapter (Member 1). Member 2's own files get their tests (7-8) from Member 2.

Uses fake AI clients only - no network call is ever made.
"""

import json

import pytest

from backend.app import explain, llm_client
from backend.app.settings import Settings
from backend.app.store import StoredRun
from backend.tests.conftest import case


class FakeClient:
    """Stand-in for AMDTokenFactoryClient. `replies` is a list of strings or exceptions."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.model = "fake-model"

    def complete(self, messages, **_):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return llm_client.Completion(content=reply, provider="amd_token_factory", model="fake-model", latency_ms=12,
                                     created_at="2026-10-16T10:00:00+00:00", request_id=None, usage={})


def good_reply(machine_id, evidence, extra_cause_ids=()):
    return json.dumps({
        "machine_id": machine_id, "summary": "s",
        "findings": [{"statement": "f", "evidence": evidence}],
        "possible_causes": [{"cause": "c", "evidence": evidence + list(extra_cause_ids)}],
        "recommended_checks": [{"action": "a", "reason": "r", "evidence": evidence}],
        "missing_information": [], "uncertainty": "u",
    })


@pytest.fixture
def amd(monkeypatch):
    """Switch explain.py to the AMD provider with a given fake client."""
    explain.clear_caches()
    monkeypatch.setattr(explain, "get_settings", lambda: Settings(llm_provider="amd_token_factory"))

    def use(fake):
        monkeypatch.setattr(explain, "make_client", lambda: fake)
        return fake

    yield use
    explain.clear_caches()


@pytest.fixture
def run(synthetic_run):
    return StoredRun(result=synthetic_run.result, is_demo=True)


# ---------------------------------------------------------------- what the AI sees


def test_llm_case_holds_only_evidence(synthetic_run):
    r = synthetic_run.result
    hp01 = case(r, "HP-01")
    c = explain.build_llm_case(r, hp01)
    assert {n["note_id"] for n in c["notes"]} == {"N-13", "N-16"}  # N-3 (unlinked) is not sent
    assert 0 < len(c["key_readings"]) <= 12
    assert all(k["row_id"] in hp01.evidence_ids for k in c["key_readings"])
    assert any(k["vibration_mm_s"] == 8.0 for k in c["key_readings"])  # real sensor values
    assert c["guidance"] and all(g["guidance"] == "general guidance, not manufacturer-verified" for g in c["guidance"])
    assert {g["fault_or_condition"] for g in c["guidance"]} == {"Vibration high", "Sound high"}


def test_metropt_guidance_is_air_leak_row(metropt_run):
    c = explain.build_llm_case(metropt_run.result, case(metropt_run.result, "APU-01"))
    assert [g["fault_or_condition"] for g in c["guidance"]] == ["Air leak"]


def test_fallback_summary_uses_only_anomalies_and_notes(synthetic_run):
    text = explain.fallback_summary(case(synthetic_run.result, "FP-02"))
    assert text.startswith("Rule-based summary (no AI): FP-02 - priority")
    assert "A-2" in text and "N-11" in text and "does not state a cause" in text


# ---------------------------------------------------------------- AMD provider through Member 2's files


def test_amd_success_becomes_inspection_report(amd, run):
    hp01 = case(run.result, "HP-01")
    a5 = next(a for a in hp01.anomalies if a.anomaly_id == "A-5")
    fake = amd(FakeClient([good_reply("HP-01", ["A-5", a5.row_ids[0]])]))
    rep = explain.explain_machine(run, "HP-01")
    assert fake.calls == 1
    assert rep.error is None and rep.explanation.summary == "s"
    assert rep.provenance.provider == "amd_token_factory" and rep.provenance.model == "fake-model"
    assert rep.grounding_rate == 1.0 and rep.unsupported == []
    assert explain.explain_machine(run, "HP-01").provenance.cached is True and fake.calls == 1


def test_amd_unknown_id_is_unsupported(amd, run):
    amd(FakeClient([good_reply("HP-01", ["A-5"], extra_cause_ids=["N-3"])]))  # N-3 is not linked evidence
    rep = explain.explain_machine(run, "HP-01")
    assert [(u.section, u.index) for u in rep.unsupported] == [("possible_causes", 0)]
    assert rep.grounding_rate == pytest.approx(0.6667)


def test_amd_invalid_json_one_repair_then_fallback(amd, run):
    fake = amd(FakeClient(["not json", "still not json"]))
    run.is_demo = False
    rep = explain.explain_machine(run, "HP-01")
    assert fake.calls == 2
    assert rep.explanation is None and rep.provenance is None and rep.grounding_rate is None
    assert rep.error and rep.fallback_summary.startswith("Rule-based summary (no AI)")


def test_amd_invalid_then_repaired(amd, run):
    fake = amd(FakeClient(["oops", good_reply("HP-01", ["A-5"])]))
    rep = explain.explain_machine(run, "HP-01")
    assert fake.calls == 2 and rep.explanation is not None


def test_amd_down_uses_saved_report_for_demo(amd, run, tmp_path, monkeypatch):
    amd(FakeClient([llm_client.LLMError("AMD Token Factory connection failed or timed out.")]))
    saved = {
        "machine_id": "HP-01",
        "explanation": {"machine_id": "HP-01", "summary": "saved", "findings": [], "possible_causes": [],
                        "recommended_checks": [], "missing_information": [], "uncertainty": "u"},
        "unsupported": [], "grounding_rate": 1.0,
        "provenance": {"provider": "amd_token_factory", "model": "m", "hardware_label": "h", "latency_ms": 900,
                       "created_at": "2026-10-17T10:00:00Z", "cached": False},
        "error": None, "fallback_summary": None,
    }
    (tmp_path / "synthetic_fleet").mkdir()
    (tmp_path / "synthetic_fleet" / "HP-01.json").write_text(json.dumps(saved), encoding="utf-8")
    monkeypatch.setattr(explain, "SAVED_REPORTS_DIR", tmp_path)
    rep = explain.explain_machine(run, "HP-01")
    assert rep.provenance.provider == "saved" and rep.provenance.cached is True
    assert rep.explanation.summary == "saved"


def test_amd_down_without_saved_report(amd, run, tmp_path, monkeypatch):
    amd(FakeClient([llm_client.LLMError("AMD Token Factory returned HTTP 503.")]))
    monkeypatch.setattr(explain, "SAVED_REPORTS_DIR", tmp_path)
    rep = explain.explain_machine(run, "HP-01")
    assert rep.explanation is None and rep.error == "AMD Token Factory returned HTTP 503."


def test_amd_missing_key_never_calls_network(monkeypatch, run, tmp_path):
    explain.clear_caches()
    monkeypatch.setattr(explain, "get_settings", lambda: Settings(llm_provider="amd_token_factory"))
    monkeypatch.setattr(explain, "SAVED_REPORTS_DIR", tmp_path)
    for var in ("AMD_TOKEN_FACTORY_API_KEY", "LLM_API_KEY", "AMD_TOKEN_FACTORY_BASE_URL", "LLM_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(llm_client, "urlopen", lambda *a, **k: pytest.fail("network call attempted"))
    rep = explain.explain_machine(run, "HP-01")
    assert rep.explanation is None and "API_KEY is not set" in rep.error
    status = explain.llm_status()
    assert status.provider == "amd_token_factory" and status.reachable is False
    explain.clear_caches()


def test_no_ai_call_for_machine_without_anomalies(amd, run):
    fake = amd(FakeClient([]))
    rep = explain.explain_machine(run, "FP-01")
    assert fake.calls == 0 and rep.explanation is None
