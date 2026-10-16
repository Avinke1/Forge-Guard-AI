"""ForgeGuard AI - AMD Token Factory smoke test (Member 2).

Run from the folder that contains backend/ :
    python3 scripts/amd_smoke_test.py            real AMD test (needs the key)
    python3 scripts/amd_smoke_test.py --mock     setup check only: no key, no network, no AI
    python3 scripts/amd_smoke_test.py --model MiMo-V2.6-Flash    test another model

The key comes from the LLM_API_KEY environment variable or backend/.env. It is NEVER printed.
Real mode uses: 1 GET without key, 1 GET /models, 1 chat request (2 if a repair is needed), 1 GET /usage.
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app import llm_client, prompts, verify  # noqa: E402

KEY_FORMAT = re.compile(r"^rc-[0-9a-fA-F]{48}$")

# One tiny hand-made case (SYNTHETIC) - enough to test JSON + evidence IDs.
CASE = {
    "machine_id": "TEST-01", "priority": "HIGH", "score": 0.8,
    "anomalies": [{
        "anomaly_id": "A-1", "sensor": "vibration_mm_s",
        "start": "2026-10-16T08:00:00", "end": "2026-10-16T08:15:00",
        "peak": 7.8, "unit": "mm/s", "method": "limit",
        "reason": "vibration 7.8 mm/s above the 6.5 mm/s limit for 2 readings",
        "row_ids": ["R1", "R2"], "severity": 0.8,
    }],
    "notes": [{
        "note_id": "N-1", "machine_id": "TEST-01", "timestamp": "2026-10-16T07:30:00",
        "text": "Operator reports the machine sounds louder than usual.",
        "source": "inspection", "synthetic": True,
    }],
    "evidence_ids": ["A-1", "R1", "R2", "N-1"],
}
READINGS = [
    {"row_id": "R1", "timestamp": "2026-10-16T08:00:00", "machine_id": "TEST-01",
     "vibration_mm_s": 7.4, "temperature_c": 71.0, "sound_db": 84.0},
    {"row_id": "R2", "timestamp": "2026-10-16T08:15:00", "machine_id": "TEST-01",
     "vibration_mm_s": 7.8, "temperature_c": 71.5, "sound_db": 86.0},
]
SENSORS = {
    "vibration_mm_s": {"label": "Vibration", "unit": "mm/s", "warn_high": 6.5, "warn_low": None},
    "temperature_c": {"label": "Temperature", "unit": "degC", "warn_high": 90, "warn_low": None},
    "sound_db": {"label": "Sound level", "unit": "dB", "warn_high": 85, "warn_low": None},
}
DATASET = {"id": "smoke_test", "name": "Smoke test (2 synthetic readings)", "synthetic": True,
           "attribution": "SYNTHETIC smoke-test data - not real plant measurements"}


def line(title: str) -> None:
    print("\n" + title)
    print("-" * len(title))


def ssl_problem(exc: BaseException) -> bool:
    reason = getattr(exc, "reason", None)
    return isinstance(exc, ssl.SSLError) or isinstance(reason, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="ForgeGuard AI - AMD Token Factory smoke test")
    parser.add_argument("--mock", action="store_true", help="setup check only (no key, no network)")
    parser.add_argument("--model", help="model to test instead of LLM_MODEL")
    args = parser.parse_args()

    if args.mock:
        cfg = llm_client.LLMConfig(provider="mock")
    else:
        cfg = llm_client.LLMConfig.from_env()
        if args.model:
            cfg.model = args.model.strip()
    client = llm_client.LLMClient(cfg)
    results: dict[str, bool] = {}

    print("FORGEGUARD AI - AMD TOKEN FACTORY SMOKE TEST")
    print(f"provider       : {cfg.provider}")
    print(f"base URL host  : {urlsplit(cfg.base_url).hostname}")
    print(f"model          : {cfg.model}   (fallback: {cfg.fallback_model})")
    print(f"hardware label : {client.hardware_label}")

    if not args.mock:
        if cfg.provider != "amd_token_factory":
            print(f"\nSTOP: LLM_PROVIDER is '{cfg.provider}'. Run:  export LLM_PROVIDER=amd_token_factory")
            return 1
        problem = cfg.problem()
        if problem:
            print(f"\nSTOP: {problem}\n  Mac:  read -s LLM_API_KEY && export LLM_API_KEY   (paste key, Enter)")
            return 1
        key_ok = bool(KEY_FORMAT.match(cfg.api_key))
        print(f"key            : set, format rc- + 48 hex: {'yes' if key_ok else 'NO - check for spaces / missing characters'}")

        # 1. request WITHOUT a key must be refused
        line("[1/4] Request without key is refused")
        try:
            resp = llm_client.urllib_transport("GET", cfg.base_url + "/models",
                                               {"Accept": "application/json", "User-Agent": llm_client.USER_AGENT},
                                               None, 15.0)
            refused = resp.status in (401, 403)
            print(f"HTTP {resp.status} -> refused without key: {'yes' if refused else 'NO'}")
            results["no-key request refused"] = refused
        except (OSError, urllib.error.URLError) as exc:
            if ssl_problem(exc):
                print("SSL certificate check failed on this computer.\n"
                      "  Mac fix: open Finder > Applications > Python 3.x > double-click 'Install Certificates.command',"
                      " then run this script again.")
            else:
                print(f"Cannot reach the AMD service: {type(exc).__name__}. Check the internet connection.")
            return 1

        # 2. model catalog
        line("[2/4] GET /v1/models (no tokens used)")
        try:
            models, ms = client.list_models()
            in_catalog = cfg.model.lower() in {m.lower() for m in models}
            print(f"{len(models)} models, {ms} ms")
            for m in models:
                print(f"  - {m}")
            print(f"LLM_MODEL '{cfg.model}' in catalog: {'yes' if in_catalog else 'NO - pick a model from the list'}")
            results["model in catalog"] = in_catalog
        except llm_client.LLMError as exc:
            print(f"FAILED ({exc.kind}): {exc.message}")
            results["model in catalog"] = False
            print("\nRESULT: FAIL")
            return 1

    # 3. one real explanation request
    line("[3/4] One explanation request (JSON + evidence IDs)" if not args.mock else "[mock] Explanation without AI")
    payload = prompts.build_case_payload(CASE, READINGS, SENSORS, DATASET)
    messages = prompts.build_messages(payload)
    try:
        result = client.generate(messages, CASE["machine_id"])
    except llm_client.LLMError as exc:
        print("valid JSON     : no")
        print(f"error ({exc.kind}): {exc.message}")
        results["valid JSON"] = False
        print("\nRESULT: FAIL")
        return 1
    _, unsupported, rate = verify.check_evidence(result.explanation, verify.allowed_evidence_ids(CASE))
    print(f"model (from API): {result.model}")
    print(f"latency         : {result.latency_ms} ms   requests: {result.requests}"
          f"   fallback model used: {'yes' if result.used_fallback_model else 'no'}")
    print("valid JSON      : yes")
    print(f"grounding rate  : {rate}   unsupported items: {len(unsupported)}")
    print(f"summary         : {result.explanation.get('summary', '')[:220]}")
    results["valid JSON"] = True
    results["grounding >= 0.8"] = rate is not None and rate >= 0.8

    # 4. usage (spend cap)
    if not args.mock:
        line("[4/4] GET /v1/usage (check before sharing: hide anything personal)")
        try:
            usage = client.usage()
            print(json.dumps(usage, ensure_ascii=False)[:900])
        except llm_client.LLMError as exc:
            print(f"(usage not available: {exc.message})")

    print("\nSUMMARY")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    passed = all(results.values())
    if args.mock:
        print("\nRESULT: SETUP OK (mock) - now run without --mock when the key is ready" if passed else "\nRESULT: FAIL")
    else:
        print("\nRESULT: PASS - AMD Token Factory works" if passed else "\nRESULT: FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
