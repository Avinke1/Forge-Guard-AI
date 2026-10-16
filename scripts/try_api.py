"""Try the running ForgeGuard backend over HTTP (same commands on macOS and Windows).

Start the backend first:  python -m uvicorn backend.app.main:app --port 8000
Then, in a second terminal (from the repo root):
    python scripts/try_api.py                 quick check: health, datasets, demo queue, mock explain, LLM status
    python scripts/try_api.py --task5 --yes   Member 2 Task 5: EXACTLY 4 real AI calls, one at a time
    python scripts/try_api.py --base https://<service>.onrender.com     same checks against the deployed backend

Standard library only. It talks to the API like the website does, so every explain call goes through
main.py -> ai_view() -> reports.explain_machine. It never reads backend/.env and never prints a key.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

TASK5 = [("synthetic_fleet", "HP-01"), ("synthetic_fleet", "FP-02"), ("synthetic_fleet", "HP-02"),
         ("metropt3", "APU-01")]
WAIT_BETWEEN_AI_CALLS_S = 5
EXPLAIN_TIMEOUT_S = 120  # a real AMD explanation takes about 25 s (seen 12-36 s)


def call(base: str, method: str, path: str, timeout: float = 30) -> tuple[int, dict]:
    req = urllib.request.Request(base.rstrip("/") + path, method=method, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except ValueError:
            return exc.code, {"error": f"HTTP {exc.code}"}


def check(label: str, ok: bool, detail: str) -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: {detail}")
    return ok


def report_line(machine: str, rep: dict) -> str:
    prov = rep.get("provenance") or {}
    if rep.get("explanation") is None:
        return f"{machine}: NO AI explanation - error: {rep.get('error')}"
    return (f"{machine}: provider={prov.get('provider')} model={prov.get('model')} latency_ms={prov.get('latency_ms')} "
            f"grounding_rate={rep.get('grounding_rate')} unsupported={len(rep.get('unsupported') or [])} "
            f"cached={prov.get('cached')}")


def quick(base: str) -> int:
    print(f"ForgeGuard API check - {base}")
    try:
        status, health = call(base, "GET", "/api/health", timeout=90)  # first call may wake a sleeping host
    except (urllib.error.URLError, OSError) as exc:
        print(f"  FAIL  backend not reachable ({type(exc).__name__}). Is uvicorn running on this address?")
        return 1
    results = [check("GET /api/health", status == 200 and health.get("status") == "ok", json.dumps(health))]

    status, datasets = call(base, "GET", "/api/datasets")
    ids = [d.get("id") for d in datasets] if isinstance(datasets, list) else []
    results.append(check("GET /api/datasets", ids == ["synthetic_fleet", "metropt3"], ", ".join(map(str, ids))))

    status, syn = call(base, "POST", "/api/analyze/demo/synthetic_fleet")
    queue = [f"{c['machine_id']} {c['priority']}" for c in syn.get("cases", [])]
    results.append(check("POST /api/analyze/demo/synthetic_fleet", status == 200 and queue[:1] == ["HP-01 HIGH"],
                         "queue: " + ", ".join(queue)))
    run_id = syn.get("run_id", "")
    print(f"        run_id = {run_id}")

    status, llm = call(base, "GET", "/api/llm/status", timeout=60)
    results.append(check("GET /api/llm/status", status == 200,
                         f"provider={llm.get('provider')} model={llm.get('model')} reachable={llm.get('reachable')} "
                         f"error={llm.get('error')}"))

    if llm.get("provider") == "mock":
        status, rep = call(base, "POST", f"/api/runs/{run_id}/explain/HP-01", timeout=EXPLAIN_TIMEOUT_S)
        results.append(check("POST explain HP-01 (mock)", status == 200 and rep.get("grounding_rate") == 1.0,
                             report_line("HP-01", rep)))
    else:
        print(f"  SKIP  explain HP-01: provider is '{llm.get('provider')}', not mock - no AI call made by this check")

    status, rep = call(base, "POST", f"/api/runs/{run_id}/explain/FP-01")
    results.append(check("POST explain FP-01 (no anomalies, no AI call)",
                         status == 200 and str(rep.get("fallback_summary", "")).startswith("Rule-based summary (no AI)"),
                         str(rep.get("fallback_summary"))[:90]))

    status, err = call(base, "POST", "/api/runs/does-not-exist/explain/HP-01")
    results.append(check("unknown run -> 404 {error}", status == 404 and "error" in err, json.dumps(err)))

    print("RESULT:", "PASS" if all(results) else "FAIL")
    return 0 if all(results) else 1


def task5(base: str, yes: bool) -> int:
    status, llm = call(base, "GET", "/api/llm/status", timeout=60)
    print(f"LLM status: provider={llm.get('provider')} model={llm.get('model')} reachable={llm.get('reachable')} "
          f"error={llm.get('error')}")
    if llm.get("provider") != "amd_token_factory" or not llm.get("reachable"):
        print("STOP: the backend is not using a reachable amd_token_factory provider. Set LLM_PROVIDER=amd_token_factory "
              "and LLM_API_KEY in backend/.env, restart uvicorn, and try again.")
        return 1
    if not yes:
        print("This makes EXACTLY 4 real AI calls (shared $1/day team limit): HP-01, FP-02, HP-02, APU-01.\n"
              "Run again with --yes to start.")
        return 1

    runs: dict[str, str] = {}
    lines = []
    for i, (dataset, machine) in enumerate(TASK5):
        if dataset not in runs:
            status, res = call(base, "POST", f"/api/analyze/demo/{dataset}")
            if status != 200:
                print(f"STOP: demo analysis {dataset} failed: {res.get('error')}")
                return 1
            runs[dataset] = res["run_id"]
        if i:
            time.sleep(WAIT_BETWEEN_AI_CALLS_S)
        print(f"[{i + 1}/4] explain {machine} ({dataset}) - about 25 s ...", flush=True)
        started = time.monotonic()
        status, rep = call(base, "POST", f"/api/runs/{runs[dataset]}/explain/{machine}", timeout=EXPLAIN_TIMEOUT_S)
        line = report_line(machine, rep) + f"  (wall {time.monotonic() - started:.0f} s, HTTP {status})"
        print("      " + line)
        lines.append(line)
        if rep.get("error") and "daily" in str(rep.get("error")).lower():
            print("STOP: the team's daily AI limit is used up. Do not retry today.")
            break
    print("\nTASK 5 RESULT (paste this to Member 1):")
    for line in lines:
        print("  " + line)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Try the running ForgeGuard backend over HTTP.")
    parser.add_argument("--base", default="http://localhost:8000", help="backend address")
    parser.add_argument("--task5", action="store_true", help="Member 2 Task 5: 4 real AI calls")
    parser.add_argument("--yes", action="store_true", help="confirm the real AI calls of --task5")
    args = parser.parse_args()
    return task5(args.base, args.yes) if args.task5 else quick(args.base)


if __name__ == "__main__":
    sys.exit(main())
