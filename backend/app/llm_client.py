"""AMD Token Factory chat-completions client for ForgeGuard AI.

Python >=3.10. Standard library only. No API calls occur during import.

Environment variables (set in your shell or hosting service's secrets):
  AMD_TOKEN_FACTORY_API_KEY  required (LLM_API_KEY is a compatibility alias)
  AMD_TOKEN_FACTORY_BASE_URL default: https://developer.amd.com.cn/radeon/api/v1
  AMD_TOKEN_FACTORY_MODEL    default: DeepSeek-V4-Flash
  LLM_TIMEOUT_S              default: 45

The AMD Token Factory dashboard's displayed Base URL/model override the defaults.
Only send API keys from your backend, never from frontend JavaScript.
"""

from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://developer.amd.com.cn/radeon/api/v1"
DEFAULT_MODEL = "DeepSeek-V4-Flash"


class LLMError(RuntimeError):
    """An LLM request failed; the caller should use a labelled fallback."""


class LLMConfigurationError(LLMError):
    """No usable/secure API configuration is available."""


@dataclass(frozen=True)
class Completion:
    content: str
    provider: str
    model: str
    latency_ms: int
    created_at: str
    request_id: str | None
    usage: dict[str, Any]
    # This label states service provenance, not independently proven physical GPU identity.
    hardware_label: str = "AMD Token Factory (AMD-hosted inference; GPU identity not independently verified)"
    cached: bool = False

    def provenance(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "hardware_label": self.hardware_label,
            "latency_ms": self.latency_ms,
            "created_at": self.created_at,
            "cached": self.cached,
            "request_id": self.request_id,
            "usage": self.usage,
        }


class AMDTokenFactoryClient:
    """Minimal OpenAI-compatible client, intended for use by the Python backend."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float | None = None,
        max_attempts: int = 2,
    ) -> None:
        self._api_key = (api_key if api_key is not None else
                         os.getenv("AMD_TOKEN_FACTORY_API_KEY") or os.getenv("LLM_API_KEY") or "").strip()
        raw_url = (base_url or os.getenv("AMD_TOKEN_FACTORY_BASE_URL") or
                   os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")
        parsed = urlsplit(raw_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise LLMConfigurationError("An HTTPS AMD Token Factory Base URL is required.")
        self.base_url = raw_url
        self.model = (model or os.getenv("AMD_TOKEN_FACTORY_MODEL") or os.getenv("LLM_MODEL") or DEFAULT_MODEL).strip()
        if not self.model:
            raise LLMConfigurationError("The AMD model identifier is missing.")
        try:
            self.timeout_s = float(timeout_s if timeout_s is not None else os.getenv("LLM_TIMEOUT_S", "45"))
        except (TypeError, ValueError) as exc:
            raise LLMConfigurationError("LLM_TIMEOUT_S must be a number.") from exc
        if not (0 < self.timeout_s <= 180):
            raise LLMConfigurationError("LLM_TIMEOUT_S must be between 0 and 180 seconds.")
        if max_attempts not in (1, 2, 3):
            raise ValueError("max_attempts must be 1, 2 or 3")
        self.max_attempts = max_attempts

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 1200,
    ) -> Completion:
        if not self.configured:
            raise LLMConfigurationError("AMD_TOKEN_FACTORY_API_KEY is not set in the backend environment.")
        if not messages or any(m.get("role") not in {"system", "user", "assistant"} or
                               not isinstance(m.get("content"), str) for m in messages):
            raise ValueError("messages must contain role/content text pairs")
        if max_tokens < 1 or max_tokens > 4096:
            raise ValueError("max_tokens must be within 1..4096")

        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }, ensure_ascii=False).encode("utf-8")
        url = self.base_url if self.base_url.endswith("/chat/completions") else self.base_url + "/chat/completions"
        start = time.perf_counter()
        response: dict[str, Any] | None = None

        for attempt in range(self.max_attempts):
            request = Request(
                url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=self.timeout_s) as result:
                    response = json.loads(result.read(2_000_000).decode("utf-8"))
                break
            except HTTPError as exc:
                # Do not expose response bodies or credentials to logs or the UI.
                retryable = exc.code in {408, 429, 500, 502, 503, 504}
                if retryable and attempt + 1 < self.max_attempts:
                    time.sleep(min(4.0 * (attempt + 1), 8.0))
                    continue
                raise LLMError(f"AMD Token Factory returned HTTP {exc.code}.") from None
            except (URLError, socket.timeout, TimeoutError, OSError) as exc:
                if attempt + 1 < self.max_attempts:
                    time.sleep(min(attempt + 1, 2))
                    continue
                raise LLMError("AMD Token Factory connection failed or timed out.") from None
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise LLMError("AMD Token Factory returned an invalid API response.") from None

        try:
            if not isinstance(response, dict):
                raise TypeError("Response is not an object")
            choice = response["choices"][0]
            content = choice["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise TypeError("No assistant response text")
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("AMD Token Factory response did not contain usable assistant text.") from None

        usage = response.get("usage", {})
        return Completion(
            content=content,
            provider="amd_token_factory",
            model=str(response.get("model") or self.model),
            latency_ms=round((time.perf_counter() - start) * 1000),
            created_at=datetime.now(timezone.utc).isoformat(),
            request_id=str(response["id"]) if response.get("id") is not None else None,
            usage=usage if isinstance(usage, dict) else {},
        )
