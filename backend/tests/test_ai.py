"""Member 2 Task 8: offline tests for ForgeGuard AI verification and AMD errors.

Every AMD request uses an injected fake transport. No real network or API key is used.
"""

import json

import pytest

from backend.app import prompts, reports, verify
from backend.app.llm_client import HTTPResponse, LLMClient, LLMConfig, LLMError


TEST_URL = "https://example.test/v1"
TEST_KEY = "rc-test-only-not-a-real-key"


def explanation(findings=None):
    return {
        "machine_id": "HP-01",
        "summary": "A vibration anomaly needs technician review.",
        "findings": (
            [{"statement": "Unusual vibration was recorded.", "evidence": ["A-1"]}]
            if findings is None else findings
        ),
        "possible_causes": [{"cause": "A loose mount may be possible.", "evidence": ["A-1"]}],
        "recommended_checks": [
            {"action": "Inspect the mounting.", "reason": "General guidance", "evidence": ["A-1"]},
            {"action": "Review the sensor data.", "reason": "Check anomaly", "evidence": ["A-1"]},
        ],
        "missing_information": [],
        "uncertainty": "The exact cause is not confirmed.",
    }


def chat_ok(reply=None, *, model="self-dploy/DeepSeek-V4-Flash"):
    if reply is None:
        reply = json.dumps(explanation())
    return HTTPResponse(200, {"content-type": "application/json"}, json.dumps({
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": reply},
                     "finish_reason": "stop"}],
    }).encode())


def http_error(status, message, *, code="", headers=None):
    return HTTPResponse(status, headers or {}, json.dumps({
        "error": {"code": code, "message": message}
    }).encode())


class FakeTransport:
    def __init__(self, replies=(), *, models=None, usage=None):
        self.replies = list(replies)
        self.models = models if models is not None else HTTPResponse(
            200, {}, b'{"data":[{"id":"DeepSeek-V4-Flash"}]}'
        )
        self.usage = usage if usage is not None else HTTPResponse(200, {}, b'{"today":{}}')
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"method": method, "url": url, "headers": headers,
                           "body": json.loads(body) if body else None})
        if method == "GET":
            return self.usage if url.split("?", 1)[0].endswith("/usage") else self.models
        assert method == "POST" and url.endswith("/chat/completions")
        assert self.replies, "Unexpected extra AI call in a test"
        return self.replies.pop(0)

    @property
    def posts(self):
        return [c for c in self.calls if c["method"] == "POST"]


def amd(fake, waits=None, **overrides):
    config = LLMConfig(provider="amd_token_factory", base_url=TEST_URL, api_key=TEST_KEY,
                       **overrides)
    return LLMClient(config, transport=fake,
                     sleep=(waits.append if waits is not None else lambda _: None))


@pytest.fixture(autouse=True)
def isolate_saved_reports(tmp_path, monkeypatch):
    reports.clear_cache()
    monkeypatch.setattr(reports, "DEMO_REPORTS_DIR", tmp_path)
    yield
    reports.clear_cache()


def test_mock_client_needs_no_network():
    client = LLMClient(LLMConfig(provider="mock"))
    case = {"machine_id": "HP-01", "anomalies": [{"anomaly_id": "A-1",
            "sensor_name": "Vibration", "sensor": "vibration_mm_s", "reason": "high"}],
            "notes": [], "general_guidance": []}
    result = client.generate(prompts.build_messages(case), "HP-01")
    assert result.provider == "mock" and result.explanation["findings"]


def test_unknown_evidence_id_is_unsupported():
    checked, unsupported, rate = verify.check_evidence(
        explanation(findings=[{"statement": "A reading", "evidence": ["A-999"]}]), {"A-1"})
    assert checked["findings"][0]["evidence"] == ["A-999"]
    assert unsupported == [{"section": "findings", "index": 0}]
    assert rate == pytest.approx(0.75)  # 1 finding + 1 cause + 2 checks


def test_empty_evidence_is_unsupported():
    data = explanation(findings=[{"statement": "A reading", "evidence": []}])
    _, unsupported, rate = verify.check_evidence(data, {"A-1"})
    assert unsupported == [{"section": "findings", "index": 0}]
    assert rate == pytest.approx(0.75)


def test_grounding_two_of_three_is_point_six_six_seven():
    data = explanation()
    data["recommended_checks"] = [{"action": "Inspect", "evidence": ["A-1"]}]
    data["possible_causes"] = [{"cause": "Unknown", "evidence": ["N-999"]}]
    _, unsupported, rate = verify.check_evidence(data, {"A-1"})
    assert unsupported == [{"section": "possible_causes", "index": 0}]
    assert rate == pytest.approx(0.667)


def test_intro_and_code_fence_are_accepted():
    answer, problem = verify.parse_explanation(
        'Here is the report:\n```json\n' + json.dumps(explanation()) + '\n```', "HP-01")
    assert problem is None
    assert len(answer["findings"]) == 1


def test_empty_findings_triggers_one_repair_request():
    fake = FakeTransport([chat_ok(json.dumps(explanation(findings=[]))), chat_ok()])
    result = amd(fake).generate([{"role": "system", "content": "Rules"},
                                 {"role": "user", "content": "CASE_JSON: {}"}], "HP-01")
    assert len(fake.posts) == 2
    assert result.explanation["findings"]
    assert len(fake.posts[1]["body"]["messages"]) == 4
    assert "findings is empty" in fake.posts[1]["body"]["messages"][-1]["content"]


def test_429_retry_after_header_is_respected():
    waits = []
    fake = FakeTransport([http_error(429, "model rate limited", headers={"retry-after": "3"}), chat_ok()])
    result = amd(fake, waits).generate([], "HP-01")
    assert result.explanation["findings"]
    assert waits == [3.0]
    assert len(fake.posts) == 2


def test_429_three_times_exhausts_retries():
    waits = []
    fake = FakeTransport([http_error(429, "rate limited", headers={"retry-after": "1"}) for _ in range(3)])
    with pytest.raises(LLMError) as exc:
        amd(fake, waits).generate([], "HP-01")
    assert exc.value.kind == "rate_limit"
    assert len(fake.posts) == 3 and waits == [1.0, 1.0]


def test_daily_cap_stops_without_retry():
    fake = FakeTransport([http_error(429, "daily spending budget reached", code="daily_cost_limit")])
    with pytest.raises(LLMError) as exc:
        amd(fake).generate([], "HP-01")
    assert exc.value.kind == "daily_cap"
    assert len(fake.posts) == 1


def test_model_unsupported_tries_mimo_once():
    fake = FakeTransport([http_error(400, "model is not supported"),
                          chat_ok(model="self-dploy/MiMo-V2.6-Flash")])
    result = amd(fake).generate([], "HP-01")
    assert len(fake.posts) == 2
    assert fake.posts[0]["body"]["model"] == "DeepSeek-V4-Flash"
    assert fake.posts[1]["body"]["model"] == "MiMo-V2.6-Flash"
    assert result.used_fallback_model is True


def test_401_is_safe_auth_error():
    fake = FakeTransport([http_error(401, "Invalid token: " + TEST_KEY)])
    with pytest.raises(LLMError) as exc:
        amd(fake).generate([], "HP-01")
    assert exc.value.kind == "auth"
    assert "AMD key missing or invalid" in exc.value.message
    assert TEST_KEY not in exc.value.message
    assert len(fake.posts) == 1


def test_403_not_verified_is_safe():
    fake = FakeTransport([http_error(403, "account_not_verified", code="account_not_verified")])
    with pytest.raises(LLMError) as exc:
        amd(fake).generate([], "HP-01")
    assert exc.value.kind == "not_verified"
    assert "AMD account still in review" in exc.value.message
    assert len(fake.posts) == 1


def test_models_ok_usage_401_not_reachable():
    fake = FakeTransport(usage=http_error(401, "invalid API key"))
    status = amd(fake).status(force=True)
    assert status["provider"] == "amd_token_factory"
    assert status["reachable"] is False
    assert "key missing or invalid" in status["error"]
    assert [c["method"] for c in fake.calls] == ["GET", "GET"]
    assert fake.calls[0]["url"].endswith("/models")
    assert "/usage?" in fake.calls[1]["url"]


def test_ground_truth_label_never_reaches_case_payload():
    case = {"machine_id": "HP-01", "priority": "HIGH", "score": 9,
            "anomalies": [{"anomaly_id": "A-1", "sensor": "vibration_mm_s",
                          "row_ids": ["R1"], "peak": 8.0, "severity": 1}],
            "notes": [], "label": "SECRET_GROUND_TRUTH", "evidence_ids": ["A-1", "R1"]}
    readings = [{"row_id": "R1", "machine_id": "HP-01", "timestamp": "2026-10-16T08:00:00",
                 "vibration_mm_s": 8.0, "label": "SECRET_GROUND_TRUTH"}]
    payload = prompts.build_case_payload(case, readings=readings,
        sensors={"vibration_mm_s": {"name": "Vibration", "kind": "sensor", "unit": "mm/s"}},
        dataset={"id": "synthetic_fleet", "synthetic": True})
    serialized = json.dumps(payload)
    assert "SECRET_GROUND_TRUTH" not in serialized
    assert '"label"' not in serialized


def test_key_never_appears_in_any_http_error_message():
    for code in (400, 401, 403, 429, 500):
        fake = FakeTransport([http_error(code, "token leaked: " + TEST_KEY,
                                         headers={"retry-after": "31"})] * (2 if code == 500 else 1))
        client = amd(fake)
        with pytest.raises(LLMError) as exc:
            client.generate([], "HP-01")
        assert TEST_KEY not in exc.value.message
        assert TEST_KEY not in str(exc.value)
