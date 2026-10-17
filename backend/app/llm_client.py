"""ForgeGuard AI - step 5 (part 2): talk to the LLM.

Providers (LLM_PROVIDER in backend/.env):
  amd_token_factory  real AI on AMD GPUs through AMD Token Factory (OpenAI-compatible API)  <- our AMD part
  mock               no AI, no network: deterministic fake JSON so the UI and tests work ("MOCK - not AI output")
  saved              no live AI: reports.py serves the saved AMD reports from data/demo_reports/
  gemini             optional backup through Google's OpenAI-compatible endpoint (never shown as AMD)

HTTP uses Python's built-in urllib (same OpenAI-compatible JSON as the "openai" package), so every
retry rule below is under our control and nothing extra is installed:
  * one system message first, response_format json_object, temperature 0.2, max_tokens 1500
  * empty reply + finish_reason "length"  -> ONE retry with reasoning_effort low/none and more tokens
  * reply is not valid JSON                -> ONE repair retry, then error
  * 429 rate limit -> wait Retry-After (max 30 s) and retry, at most 2 times; daily cap -> stop at once
  * 500/502/503/504, timeout, no connection -> ONE retry
  * 400 "not supported" (model retired)     -> try LLM_FALLBACK_MODEL once
  * 401 -> "AMD key missing or invalid"; 403 account_not_verified -> "AMD account still in review"
  * ONE request at a time per backend (the whole team shares the same AMD limits)
The key is never logged and never returned in any message.
"""
from __future__ import annotations

import email.utils
import http.client
import json
import logging
import os
import random
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlsplit

from . import prompts
from .verify import parse_explanation

log = logging.getLogger("forgeguard.llm")

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BASE_URL = "https://developer.amd.com.cn/radeon/api/v1"
DEFAULT_MODEL = "DeepSeek-V4-Flash"
DEFAULT_FALLBACK_MODEL = "MiMo-V2.6-Flash"
AMD_HARDWARE_LABEL = "AMD GPUs - AMD Token Factory (Radeon Cloud)"
GEMINI_HARDWARE_LABEL = "Google Gemini API (not AMD)"
MOCK_HARDWARE_LABEL = "none - MOCK output, not AI"
MOCK_MODEL = "mock"

PROVIDERS = ("amd_token_factory", "mock", "saved", "gemini")
LIVE_PROVIDERS = ("amd_token_factory", "gemini")

MAX_RATE_LIMIT_RETRIES = 2
MAX_WAIT_S = 30.0               # longer Retry-After -> give up now (saved report / fallback is shown)
STATUS_CACHE_S = 30.0
USER_AGENT = "ForgeGuard-AI/1.0"

_REQUEST_LOCK = threading.Lock()   # ONE AI request at a time per backend process


# --------------------------------------------------------------------------------------
# Errors and results
# --------------------------------------------------------------------------------------
class LLMError(Exception):
    """AI call failed. .message is plain English and safe to show in the UI (no key, no URL)."""

    def __init__(self, message: str, kind: str = "error", status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.kind = kind            # config | auth | not_verified | rate_limit | daily_cap | timeout |
        self.status = status        # unreachable | server | bad_request | model_unsupported | bad_json


@dataclass
class LLMResult:
    explanation: dict           # already parsed + cleaned by verify.parse_explanation
    raw_text: str
    provider: str
    model: str                  # the model name the API returned
    latency_ms: int             # time of the HTTP calls (waits for rate limits not included)
    used_fallback_model: bool = False
    requests: int = 1


# --------------------------------------------------------------------------------------
# Settings (read from backend/.env)
# --------------------------------------------------------------------------------------
def _load_env_files() -> None:
    """Load backend/.env (and a repo-root .env) into os.environ; real env vars win."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for path in (REPO_ROOT / "backend" / ".env", REPO_ROOT / ".env"):
        if path.exists():
            load_dotenv(path, override=False)


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _env_num(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(_env(name, str(default)))
    except ValueError:
        log.warning("%s is not a number - using %s", name, default)
        return default
    return max(low, min(high, value))


@dataclass
class LLMConfig:
    provider: str = "mock"
    base_url: str = DEFAULT_BASE_URL
    api_key: str = field(default="", repr=False)          # never printed
    model: str = DEFAULT_MODEL
    fallback_model: str = DEFAULT_FALLBACK_MODEL
    hardware_label: str = AMD_HARDWARE_LABEL
    timeout_s: float = 60.0
    max_cases: int = 5
    max_tokens: int = 1500
    temperature: float = 0.2

    @classmethod
    def from_env(cls) -> "LLMConfig":
        _load_env_files()
        provider = _env("LLM_PROVIDER", "mock").lower()
        if provider in ("amd", "amd_tokenfactory", "token_factory"):
            provider = "amd_token_factory"
        default_label = {"amd_token_factory": AMD_HARDWARE_LABEL,
                         "gemini": GEMINI_HARDWARE_LABEL}.get(provider, MOCK_HARDWARE_LABEL)
        return cls(
            provider=provider,
            base_url=_env("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            api_key=_env("LLM_API_KEY"),
            model=_env("LLM_MODEL", DEFAULT_MODEL),
            fallback_model=_env("LLM_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL),
            hardware_label=_env("LLM_HARDWARE_LABEL", default_label),
            timeout_s=_env_num("LLM_TIMEOUT_S", 60, 5, 180),
            max_cases=int(_env_num("LLM_MAX_CASES", 5, 1, 50)),
            max_tokens=int(_env_num("LLM_MAX_TOKENS", 1500, 200, 8000)),
            temperature=_env_num("LLM_TEMPERATURE", 0.2, 0.0, 1.0),
        )

    def problem(self) -> str | None:
        """Plain-English config problem, or None if the config can be used."""
        if self.provider not in PROVIDERS:
            return f"LLM_PROVIDER '{self.provider}' is not valid. Use one of: {', '.join(PROVIDERS)}."
        if self.provider not in LIVE_PROVIDERS:
            return None
        parts = urlsplit(self.base_url)
        local = parts.hostname in ("localhost", "127.0.0.1")
        if parts.scheme != "https" and not (parts.scheme == "http" and local):
            return "LLM_BASE_URL must start with https://"
        if not parts.netloc or parts.username or parts.password or parts.query:
            return "LLM_BASE_URL is not a valid API base URL."
        if self.provider == "gemini" and "amd.com" in (parts.hostname or ""):
            return "LLM_PROVIDER is gemini but LLM_BASE_URL points to AMD - set the Gemini base URL."
        if not self.api_key:
            return ("AMD key missing - put LLM_API_KEY in backend/.env." if self.provider == "amd_token_factory"
                    else "API key missing - put LLM_API_KEY in backend/.env.")
        if not self.model:
            return "LLM_MODEL is empty."
        return None


# --------------------------------------------------------------------------------------
# HTTP transport (replaceable in tests - no real API calls needed)
# --------------------------------------------------------------------------------------
@dataclass
class HTTPResponse:
    status: int
    headers: dict           # lower-case header names
    body: bytes


Transport = Callable[[str, str, dict, Optional[bytes], float], HTTPResponse]


def urllib_transport(method: str, url: str, headers: dict, body: bytes | None, timeout: float) -> HTTPResponse:
    """Real HTTPS call. Network problems raise OSError / TimeoutError (handled by the client)."""
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return HTTPResponse(resp.status, {k.lower(): v for k, v in resp.headers.items()},
                                resp.read(4_000_000))
    except urllib.error.HTTPError as exc:             # 4xx / 5xx still carry headers + JSON body
        try:
            data = exc.read(200_000) or b""
        except (OSError, http.client.HTTPException):
            data = b""
        headers_out = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
        return HTTPResponse(exc.code, headers_out, data)


# --------------------------------------------------------------------------------------
# Mock provider: deterministic fake answer built only from the case payload
# --------------------------------------------------------------------------------------
def mock_explanation(payload: dict | None) -> dict:
    payload = payload or {}
    machine = payload.get("machine_id") or "unknown"
    anomalies = payload.get("anomalies") or []
    notes = payload.get("notes") or []
    guidance = payload.get("general_guidance") or []

    findings = []
    for a in anomalies[:4]:
        evidence = [a.get("anomaly_id")] + ([a["first_row"]] if a.get("first_row") else [])
        findings.append({"statement": f"MOCK: {a.get('sensor_name') or a.get('sensor')} - {a.get('reason')}",
                         "evidence": [e for e in evidence if e]})
    causes = []
    for n in notes:
        links = n.get("links") or []
        if links and len(causes) < 3:
            causes.append({"cause": f"MOCK: possibly related to note {n.get('note_id')} "
                                    f"({links[0].get('relation')} {links[0].get('anomaly_id')}).",
                           "evidence": [links[0].get("anomaly_id"), n.get("note_id")]})
    checks = []
    top = anomalies[0].get("anomaly_id") if anomalies else None
    for g in guidance[:3]:
        if top:
            checks.append({"action": f"MOCK: {g.get('action')}",
                           "reason": f"({prompts.GUIDANCE_LABEL})", "evidence": [top]})
    summary = f"MOCK - not AI output. {machine}: {len(anomalies)} unusual reading pattern(s)"
    if anomalies:
        summary += f"; strongest: {anomalies[0].get('reason')}"
    return {
        "machine_id": machine,
        "summary": summary + ".",
        "findings": findings,
        "possible_causes": causes,
        "recommended_checks": checks,
        "missing_information": ["MOCK output - set LLM_PROVIDER=amd_token_factory for a real AI explanation."],
        "uncertainty": "MOCK output - not written by an AI model.",
    }


def mock_transport(method: str, url: str, headers: dict, body: bytes | None, timeout: float) -> HTTPResponse:
    """Answers like the OpenAI-compatible API, without any network."""
    if method == "GET":
        if url.rstrip("/").endswith("/models"):
            return HTTPResponse(200, {}, json.dumps({"object": "list", "data": [{"id": MOCK_MODEL}]}).encode())
        return HTTPResponse(404, {}, b'{"error": {"message": "not found"}}')
    request = json.loads((body or b"{}").decode("utf-8"))
    payload = prompts.payload_from_messages(request.get("messages") or [])
    content = json.dumps(mock_explanation(payload), ensure_ascii=False)
    answer = {"id": "mock", "object": "chat.completion", "model": MOCK_MODEL,
              "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                           "finish_reason": "stop"}],
              "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
    return HTTPResponse(200, {"content-type": "application/json"}, json.dumps(answer).encode("utf-8"))


# --------------------------------------------------------------------------------------
# Helpers for API answers
# --------------------------------------------------------------------------------------
def parse_error_body(body: bytes) -> tuple[str, str, str]:
    """(code, type, message) from {"error": {...}} or {"detail": {"error": {...}}} (or plain text)."""
    text = (body or b"").decode("utf-8", "replace")
    try:
        data = json.loads(text)
    except ValueError:
        return "", "", text[:300]
    err: Any = None
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(data.get("error"), dict):
            err = data["error"]
        elif isinstance(detail, dict) and isinstance(detail.get("error"), dict):
            err = detail["error"]
        elif isinstance(data.get("error"), str):
            err = {"message": data["error"]}
        elif isinstance(detail, str):
            err = {"message": detail}
        elif "message" in data:
            err = data
    if not isinstance(err, dict):
        return "", "", str(data)[:300]
    return (str(err.get("code") or ""), str(err.get("type") or ""), str(err.get("message") or "")[:300])


def retry_after_seconds(headers: dict, attempt: int) -> float:
    """Seconds to wait: the Retry-After header (seconds or HTTP date), else backoff with jitter."""
    raw = (headers or {}).get("retry-after")
    if raw:
        try:
            return max(1.0, float(raw))
        except ValueError:
            try:
                when = email.utils.parsedate_to_datetime(raw)
                return max(1.0, (when - datetime.now(when.tzinfo or timezone.utc)).total_seconds())
            except (TypeError, ValueError):
                pass
    return min(MAX_WAIT_S, 2.0 * (2 ** (attempt - 1))) + random.uniform(0, 1)


def _looks_like_daily_cap(text: str) -> bool:
    return any(w in text for w in ("daily", "spend", "budget", "quota", "insufficient", "credit"))


def _looks_like_model_problem(text: str) -> bool:
    if "not supported" in text or "not_supported" in text:
        return True
    return "model" in text and any(w in text for w in (
        "not found", "not_found", "does not exist", "retired", "unknown", "not available", "unavailable", "no such"))


def _is_mimo(model: str) -> bool:
    return model.lower().startswith("mimo")


def _is_timeout(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    return isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, (TimeoutError, socket.timeout))


def _read_choice(data: dict) -> tuple[str, str | None, str | None]:
    """(content, finish_reason, model) from a chat.completion answer."""
    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return "", None, data.get("model")
    choice = choices[0]
    message = choice.get("message") or {}
    content = message.get("content")
    if isinstance(content, list):                       # some servers send content parts
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return (content if isinstance(content, str) else ""), choice.get("finish_reason"), data.get("model")


# --------------------------------------------------------------------------------------
# The client
# --------------------------------------------------------------------------------------
class LLMClient:
    def __init__(self, config: LLMConfig | None = None, transport: Transport | None = None,
                 sleep: Callable[[float], None] | None = None) -> None:
        self.config = config or LLMConfig.from_env()
        if transport is not None:
            self._transport = transport
        elif self.config.provider == "mock":
            self._transport = mock_transport
        else:
            self._transport = urllib_transport
        self._sleep = sleep or time.sleep
        self.last_latency_ms: int | None = None
        self._status_cache: dict | None = None
        self._status_time = 0.0
        self._status_lock = threading.Lock()

    # ---- public facts -----------------------------------------------------------------
    @property
    def provider(self) -> str:
        return self.config.provider

    @property
    def hardware_label(self) -> str:
        """Honest label: only the amd_token_factory provider may mention AMD."""
        label = self.config.hardware_label
        if self.provider == "mock":
            return MOCK_HARDWARE_LABEL
        if self.provider != "amd_token_factory" and "AMD" in label.upper():
            return GEMINI_HARDWARE_LABEL if self.provider == "gemini" else MOCK_HARDWARE_LABEL
        return label

    @property
    def _service(self) -> str:
        return {"amd_token_factory": "AMD Token Factory", "gemini": "Gemini API"}.get(self.provider, "the AI service")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json",
                "Accept": "application/json", "User-Agent": USER_AGENT}

    def _redact(self, text: str) -> str:
        text = re.sub(r"rc-[0-9a-fA-F]{8,}", "rc-***", text or "")
        if self.config.api_key:
            text = text.replace(self.config.api_key, "***")
        return text

    # ---- explanation --------------------------------------------------------------------
    def generate(self, messages: list[dict], machine_id: str) -> LLMResult:
        """Send ONE machine case and return the parsed explanation. Raises LLMError."""
        problem = self.config.problem()
        if problem:
            raise LLMError(problem, "config")
        if self.provider == "saved":
            raise LLMError("LLM_PROVIDER is 'saved': only saved reports are used, no live AI.", "config")
        with _REQUEST_LOCK:
            return self._generate_locked(messages, machine_id)

    def _chat_body(self, model: str, messages: list[dict], max_tokens: int, reasoning: str | None) -> dict:
        body = {
            "model": model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        if self.provider == "amd_token_factory":
            if reasoning:
                body["reasoning_effort"] = reasoning
            elif _is_mimo(model):
                body["reasoning_effort"] = "none"
        return body

    def _generate_locked(self, messages: list[dict], machine_id: str) -> LLMResult:
        model = self.config.model
        max_tokens = self.config.max_tokens
        reasoning: str | None = None
        current = list(messages)
        used_fallback = length_retry_done = repair_done = False
        http_ms = requests = 0

        while True:
            body = self._chat_body(model, current, max_tokens, reasoning)
            try:
                data, ms = self._post_chat(body, model)
            except LLMError as exc:
                fallback = self.config.fallback_model
                if (exc.kind == "model_unsupported" and not used_fallback and fallback
                        and fallback.lower() != model.lower()):
                    log.warning("Model %s not supported - trying fallback model %s once", model, fallback)
                    model, used_fallback, reasoning = fallback, True, None
                    continue
                raise
            requests += 1
            http_ms += ms
            content, finish, answered_model = _read_choice(data)

            if not content.strip() and finish == "length" and not length_retry_done:
                length_retry_done = True          # thinking used all tokens -> less thinking, more tokens
                reasoning = None if self.provider == "gemini" else ("none" if _is_mimo(model) else "low")
                max_tokens = min(max(max_tokens * 2, 3000), 8000)
                log.warning("Empty AI reply (finish_reason=length) - one retry with reasoning_effort=%s", reasoning)
                continue

            explanation, problem = parse_explanation(content, machine_id)
            if explanation is not None:
                self.last_latency_ms = http_ms
                return LLMResult(explanation=explanation, raw_text=content, provider=self.provider,
                                 model=str(answered_model or model), latency_ms=http_ms,
                                 used_fallback_model=used_fallback, requests=requests)
            if repair_done:
                raise LLMError(f"The AI reply could not be used, even after one repair try ({problem}).", "bad_json")
            repair_done = True
            log.warning("AI reply not usable (%s) - one repair retry", problem)
            current = prompts.build_repair_messages(messages, content, problem)

    def _post_chat(self, body: dict, model: str) -> tuple[dict, int]:
        """POST /chat/completions with the retry rules. Returns (answer JSON, latency ms)."""
        url = self.config.base_url + "/chat/completions"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        rate_retries = transient_retries = 0
        while True:
            start = time.monotonic()
            try:
                resp = self._transport("POST", url, self._headers(), data, self.config.timeout_s)
            except (OSError, http.client.HTTPException) as exc:
                kind = "timeout" if _is_timeout(exc) else "unreachable"
                if transient_retries < 1:
                    transient_retries += 1
                    log.warning("%s %s - one retry", self._service, kind)
                    self._sleep(2.0)
                    continue
                raise self._network_error(kind) from None
            ms = int((time.monotonic() - start) * 1000)

            if 200 <= resp.status < 300:
                try:
                    answer = json.loads(resp.body.decode("utf-8"))
                except (UnicodeError, ValueError):
                    raise LLMError(f"{self._service} sent an answer that is not JSON.", "server", resp.status) from None
                if not isinstance(answer, dict):
                    raise LLMError(f"{self._service} sent an unexpected answer.", "server", resp.status)
                return answer, ms

            error = self._error_for(resp, model)
            if error.kind == "rate_limit" and rate_retries < MAX_RATE_LIMIT_RETRIES:
                wait = retry_after_seconds(resp.headers, rate_retries + 1)
                if wait <= MAX_WAIT_S:
                    rate_retries += 1
                    log.warning("Rate limit (429) - waiting %.1f s, retry %d of %d",
                                wait, rate_retries, MAX_RATE_LIMIT_RETRIES)
                    self._sleep(wait)
                    continue
                error = LLMError(f"Rate limit reached on {self._service} (the whole team shares it). "
                                 f"Try again in about {int(wait)} s.", "rate_limit", resp.status)
            elif error.kind == "server" and transient_retries < 1 and resp.status in (500, 502, 503, 504):
                transient_retries += 1
                log.warning("%s HTTP %s - one retry", self._service, resp.status)
                self._sleep(2.0 + random.uniform(0, 1))
                continue
            raise error

    def _network_error(self, kind: str) -> LLMError:
        if kind == "timeout":
            return LLMError(f"{self._service} did not answer in time ({int(self.config.timeout_s)} s). "
                            "Try again in a minute.", "timeout")
        return LLMError(f"Cannot reach {self._service} (no connection). Check the internet connection.", "unreachable")

    def _error_for(self, resp: HTTPResponse, model: str) -> LLMError:
        """Turn an error answer into a plain-English LLMError. The server's own text only goes to the log."""
        code, etype, msg = parse_error_body(resp.body)
        text = f"{code} {etype} {msg}".lower()
        status = resp.status
        log.warning("%s HTTP %s: %s", self._service, status, self._redact(f"{code} {etype} {msg}".strip()))
        svc = self._service
        if status == 402 or (status == 429 and _looks_like_daily_cap(text)):
            return LLMError(f"The team's daily AI limit on {svc} is used up. Saved reports or the rule-based "
                            "summary are shown until it resets.", "daily_cap", status)
        if status == 429:
            return LLMError(f"Rate limit reached on {svc} (the whole team shares it). Wait a minute and try again.",
                            "rate_limit", status)
        if status in (500, 502, 503, 504):
            return LLMError(f"{svc} is temporarily unavailable (HTTP {status}). Try again in a minute.", "server", status)
        if status == 401:
            name = "AMD key" if self.provider == "amd_token_factory" else "API key"
            return LLMError(f"{name} missing or invalid (HTTP 401). Check LLM_API_KEY in backend/.env.", "auth", status)
        if status == 403:
            if "not_verified" in text or "verif" in text or "review" in text:
                return LLMError("AMD account still in review (HTTP 403). Wait until AMD verifies the account.",
                                "not_verified", status)
            return LLMError(f"{svc} refused the request (HTTP 403).", "auth", status)
        if status in (400, 404, 422) and _looks_like_model_problem(text):
            return LLMError(f"Model '{model}' is not supported on {svc} any more. "
                            "Check GET /v1/models and update LLM_MODEL.", "model_unsupported", status)
        if status in (400, 413, 422):
            return LLMError(f"{svc} rejected the request (HTTP {status}). See the backend log.", "bad_request", status)
        return LLMError(f"Unexpected answer from {svc} (HTTP {status}).", "server", status)

    # ---- catalog, usage, status ---------------------------------------------------------
    def _get_json(self, path: str) -> tuple[Any, int]:
        problem = self.config.problem()
        if problem:
            raise LLMError(problem, "config")
        url = self.config.base_url + path
        start = time.monotonic()
        try:
            resp = self._transport("GET", url, self._headers(), None, min(15.0, self.config.timeout_s))
        except (OSError, http.client.HTTPException) as exc:
            raise self._network_error("timeout" if _is_timeout(exc) else "unreachable") from None
        ms = int((time.monotonic() - start) * 1000)
        if not 200 <= resp.status < 300:
            raise self._error_for(resp, self.config.model)
        try:
            return json.loads(resp.body.decode("utf-8")), ms
        except (UnicodeError, ValueError):
            raise LLMError(f"{self._service} sent an answer that is not JSON.", "server", resp.status) from None

    def list_models(self) -> tuple[list[str], int]:
        """Model IDs from GET /v1/models (no tokens used) and the latency in ms."""
        data, ms = self._get_json("/models")
        items = data.get("data", []) if isinstance(data, dict) else data
        ids = [str(m.get("id")) for m in items or [] if isinstance(m, dict) and m.get("id")]
        return ids, ms

    def usage(self) -> dict:
        """Raw answer of GET /v1/usage?include_recent=true (for the smoke test / AMD evidence)."""
        data, _ = self._get_json("/usage?include_recent=true")
        return data if isinstance(data, dict) else {"data": data}

    def status(self, force: bool = False) -> dict:
        """LLMStatus {provider, model, hardware_label, reachable, last_latency_ms, error}, cached 30 s."""
        with self._status_lock:
            if (not force and self._status_cache is not None
                    and time.monotonic() - self._status_time < STATUS_CACHE_S):
                return dict(self._status_cache)
        result = self._check_status()
        with self._status_lock:
            self._status_cache, self._status_time = result, time.monotonic()
        return dict(result)

    def _check_status(self) -> dict:
        st = {"provider": self.provider, "model": self.config.model, "hardware_label": self.hardware_label,
              "reachable": False, "last_latency_ms": self.last_latency_ms, "error": None}
        if self.provider == "mock":
            st.update(model=MOCK_MODEL, reachable=True)
            return st
        if self.provider == "saved":
            st.update(model="saved reports", reachable=True)
            return st
        problem = self.config.problem()
        if problem:
            st["error"] = problem
            return st
        try:
            models, ms = self.list_models()
        except LLMError as exc:
            st["error"] = exc.message
            return st
        st["reachable"] = True
        if st["last_latency_ms"] is None:
            st["last_latency_ms"] = ms
        if self.provider == "amd_token_factory":
            # GET /v1/models can answer even with a wrong key, so check the key with GET /v1/usage
            # (no tokens used). A wrong key must never show as "AMD ready" in the UI.
            try:
                self.usage()
            except LLMError as exc:
                if exc.kind in ("auth", "not_verified"):
                    st["reachable"] = False
                    st["error"] = exc.message
                    return st
        if models and self.config.model.lower() not in {m.lower() for m in models}:
            st["error"] = (f"Model '{self.config.model}' is not in the {self._service} model list "
                           "(GET /v1/models). Choose another LLM_MODEL.")
        return st


# --------------------------------------------------------------------------------------
# One shared client per backend process
# --------------------------------------------------------------------------------------
_CLIENT: LLMClient | None = None
_CLIENT_LOCK = threading.Lock()


def get_client() -> LLMClient:
    global _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is None:
            _CLIENT = LLMClient()
            log.info("LLM provider: %s, model: %s", _CLIENT.provider, _CLIENT.config.model)
        return _CLIENT


def set_client(client: LLMClient | None) -> None:
    """Replace the shared client (tests, or after changing .env). None = rebuild from .env on next use."""
    global _CLIENT
    with _CLIENT_LOCK:
        _CLIENT = client
