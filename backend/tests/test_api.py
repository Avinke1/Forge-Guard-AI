"""Test 9 (API) and test 10 (label never in API output or prompt) - CLAUDE.md section 11."""

import json

import pytest
from fastapi.testclient import TestClient

from backend.app import llm_client, prompts, reports
from backend.app.main import app
from backend.app.pipeline import ai_view
from backend.app.settings import REPO_ROOT

SYN_READINGS = REPO_ROOT / "data/processed/synthetic_fleet/readings.csv"
SYN_NOTES = REPO_ROOT / "data/processed/synthetic_fleet/notes.csv"


@pytest.fixture(scope="module")
def client():
    reports.clear_cache()
    llm_client.set_client(None)  # rebuilt from the environment: LLM_PROVIDER=mock (conftest)
    return TestClient(app)


@pytest.fixture(scope="module")
def syn(client):
    r = client.post("/api/analyze/demo/synthetic_fleet")
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def met(client):
    r = client.post("/api/analyze/demo/metropt3")
    assert r.status_code == 200
    return r.json()


def _error(r, status):
    assert r.status_code == status, r.text
    body = r.json()
    assert set(body) == {"error"} and body["error"]
    return body["error"]


# ---------------------------------------------------------------- basics


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["version"]


def test_datasets(client):
    data = client.get("/api/datasets").json()
    assert [d["id"] for d in data] == ["synthetic_fleet", "metropt3"]
    by_id = {d["id"]: d for d in data}
    assert by_id["synthetic_fleet"]["synthetic"] is True
    assert by_id["synthetic_fleet"]["attribution"] == "SYNTHETIC demo data - not real plant measurements"
    assert by_id["metropt3"]["attribution"] == (
        "Real data: MetroPT-3 dataset (UCI Machine Learning Repository, CC BY 4.0)"
    )
    assert all(d["description"] for d in data)


def test_unknown_route_is_json_error(client):
    _error(client.get("/api/nope"), 404)


# ---------------------------------------------------------------- demo analyses


def test_demo_synthetic(syn):
    assert syn["dataset"]["id"] == "synthetic_fleet" and syn["validation"]["ok"]
    assert [c["machine_id"] for c in syn["cases"]][0] == "HP-01"
    assert len(syn["readings"]) == 1724 and len(syn["notes"]) == 20
    assert syn["sensors"]["vibration_mm_s"]["warn_high"] == 6.5


def test_demo_metropt(met):
    assert met["dataset"]["synthetic"] is False
    assert met["cases"][0]["machine_id"] == "APU-01" and met["cases"][0]["anomalies"]
    assert met["sensors"]["raw_rows"]["kind"] == "quality"


def test_demo_unknown_dataset(client):
    _error(client.post("/api/analyze/demo/ai4i"), 404)
    _error(client.post("/api/analyze/demo/nope"), 404)


# ---------------------------------------------------------------- explain (mock provider)


def test_explain_mock_hp01(client, syn):
    r = client.post(f"/api/runs/{syn['run_id']}/explain/HP-01")
    assert r.status_code == 200
    rep = r.json()
    assert rep["machine_id"] == "HP-01" and rep["error"] is None
    assert rep["explanation"]["summary"].startswith("MOCK - not AI output")
    assert rep["provenance"]["provider"] == "mock" and rep["provenance"]["cached"] is False
    assert rep["grounding_rate"] == 1.0 and rep["unsupported"] == []
    again = client.post(f"/api/runs/{syn['run_id']}/explain/HP-01").json()
    assert again["provenance"]["cached"] is True


def test_explain_mock_metropt(client, met):
    rep = client.post(f"/api/runs/{met['run_id']}/explain/APU-01").json()
    assert rep["explanation"] is not None and rep["grounding_rate"] == 1.0


def test_explain_machine_without_anomalies(client, syn):
    rep = client.post(f"/api/runs/{syn['run_id']}/explain/FP-01").json()
    assert rep["explanation"] is None and rep["provenance"] is None and rep["grounding_rate"] is None
    assert rep["error"] and rep["fallback_summary"].startswith("Rule-based summary (no AI)")


def test_explain_unknown_run_or_machine(client, syn):
    _error(client.post("/api/runs/does-not-exist/explain/HP-01"), 404)
    _error(client.post(f"/api/runs/{syn['run_id']}/explain/XX-99"), 404)


def test_llm_status_mock(client):
    s = client.get("/api/llm/status").json()
    assert s["provider"] == "mock" and s["reachable"] is True and s["error"] is None


# ---------------------------------------------------------------- uploads


def test_upload_txt_rejected(client):
    msg = _error(client.post("/api/analyze", files={"readings": ("readings.txt", b"a,b\n1,2\n", "text/plain")}), 400)
    assert ".csv" in msg


def test_upload_without_machine_id(client):
    csv = b"timestamp,vibration_mm_s\n2026-10-14T00:00:00,2.1\n"
    msg = _error(client.post("/api/analyze", files={"readings": ("r.csv", csv, "text/csv")}), 400)
    assert "machine_id" in msg


def test_upload_too_large(client):
    big = b"a" * (10 * 1024 * 1024 + 1)
    assert "too large" in _error(client.post("/api/analyze", files={"readings": ("r.csv", big, "text/csv")}), 400)


def test_upload_missing_readings_field(client):
    assert "readings" in _error(client.post("/api/analyze", data={"dataset_hint": "metropt3"}), 400)


def test_upload_unknown_columns(client):
    csv = b"timestamp,machine_id,colour\n2026-10-14T00:00:00,X,red\n"
    _error(client.post("/api/analyze", files={"readings": ("r.csv", csv, "text/csv")}), 400)


def test_upload_synthetic_files(client):
    files = {
        "readings": ("readings.csv", SYN_READINGS.read_bytes(), "text/csv"),
        "notes": ("notes.csv", SYN_NOTES.read_bytes(), "text/csv"),
    }
    r = client.post("/api/analyze", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["dataset"]["id"] == "synthetic_fleet" and body["cases"][0]["machine_id"] == "HP-01"
    assert len(body["notes"]) == 20
    rep = client.post(f"/api/runs/{body['run_id']}/explain/HP-01").json()
    assert rep["provenance"]["provider"] == "mock"


def test_upload_with_dataset_hint(client):
    csv = b"timestamp,machine_id,tp2_bar,label\n2020-07-08T15:20:00,APU-01,6.3,0\n2020-07-08T15:25:00,APU-01,6.1,0\n"
    r = client.post("/api/analyze", files={"readings": ("m.csv", csv, "text/csv")}, data={"dataset_hint": "metropt3"})
    assert r.status_code == 200 and r.json()["dataset"]["id"] == "metropt3"
    _error(client.post("/api/analyze", files={"readings": ("m.csv", csv, "text/csv")}, data={"dataset_hint": "x"}), 400)


# ---------------------------------------------------------------- CORS


def test_cors_allows_local_frontend_only(client):
    ok = client.options("/api/health", headers={"Origin": "http://localhost:5173",
                                                 "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/api/health", headers={"Origin": "https://evil.example",
                                                  "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


# ---------------------------------------------------------------- test 10: label never leaves validation


def test_label_not_in_api_output(syn, met):
    for body in (syn, met):
        assert all("label" not in r for r in body["readings"])
        assert '"label"' not in json.dumps(body["cases"])


def test_label_and_answer_key_not_in_prompt(client, syn, met):
    from backend.app.store import runs

    for body in (syn, met):
        view = ai_view(runs.get(body["run_id"]).result)
        for case in view.cases:
            payload = prompts.build_case_payload(case, readings=view.readings, sensors=view.sensors,
                                                 dataset=view.dataset)
            text = json.dumps(payload) + json.dumps(prompts.build_messages(payload))
            assert '"label"' not in text
            assert "fault_events" not in text and "event_id" not in text


def test_no_secrets_or_urls_in_responses(client, syn):
    s = client.get("/api/llm/status").text + client.get("/api/health").text
    assert "http" not in s.lower() and "key" not in s.lower()


# ---------------------------------------------------------------- run history (read-only, in memory)


def test_runs_list_newest_first(client, syn, met):
    newest = client.post("/api/analyze/demo/synthetic_fleet").json()
    rows = client.get("/api/runs").json()
    assert rows[0]["run_id"] == newest["run_id"] and len(rows) <= 20
    assert [r["created_at"] for r in rows] == sorted((r["created_at"] for r in rows), reverse=True)
    by_id = {r["run_id"]: r for r in rows}
    for body, real in ((syn, False), (met, True)):
        row = by_id[body["run_id"]]
        assert set(row) == {"run_id", "created_at", "dataset_id", "dataset_name", "real", "machines", "counts"}
        assert row["dataset_id"] == body["dataset"]["id"] and row["dataset_name"] == body["dataset"]["name"]
        assert row["real"] is real and row["machines"] == len(body["cases"])
        expected = {p: sum(c["priority"] == p for c in body["cases"]) for p in ("HIGH", "MEDIUM", "LOW", "OK")}
        assert row["counts"] == expected
        assert "T" in row["created_at"] and "+" not in row["created_at"] and not row["created_at"].endswith("Z")


def test_get_run(client, syn):
    assert client.get(f"/api/runs/{syn['run_id']}").json() == syn
    assert "Run not found" in _error(client.get("/api/runs/does-not-exist"), 404)


def test_run_store_keeps_newest_only():
    from types import SimpleNamespace

    from backend.app.store import RunStore

    store = RunStore(3)
    for i in range(5):
        store.put(SimpleNamespace(run_id=f"r{i}"), is_demo=True)
    assert [r.result.run_id for r in store.newest_first()] == ["r4", "r3", "r2"]
    assert store.get("r0") is None and len(store) == 3
