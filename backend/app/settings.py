"""Runtime settings read from environment variables and .env files.

Lookup order (later wins): repo-root .env, then backend/.env, then real environment variables.
Secrets (LLM_API_KEY) are stored as SecretStr so they never appear in repr() or logs.

The .env values are ALSO exported to os.environ (real environment variables are never overridden),
because Member 2's llm_client.py reads AMD_TOKEN_FACTORY_* with os.getenv.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.app import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"

# backend/.env first, so it wins over a repo-root .env (same priority as Settings below).
for _env_file in (BACKEND_DIR / ".env", REPO_ROOT / ".env"):
    if _env_file.is_file():
        load_dotenv(_env_file, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_version: str = __version__

    # LLM (Member 2). Defaults are safe: mock provider, no endpoint, no key.
    # Wired in explain.py: mock, amd_token_factory. amd_vllm / gemini are reserved (not connected).
    llm_provider: Literal["mock", "amd_token_factory", "amd_vllm", "gemini"] = "mock"
    llm_base_url: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_hardware_label: str = ""
    llm_timeout_s: float = 60.0
    llm_max_cases: int = 5

    # API
    frontend_origins: str = "http://localhost:5173"
    # Optional regex for extra origins, e.g. Vercel preview URLs: https://forgeguard-[a-z0-9-]+\.vercel\.app
    frontend_origin_regex: str = ""
    max_upload_mb: int = 10
    max_runs: int = 20

    @property
    def frontend_origin_list(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
