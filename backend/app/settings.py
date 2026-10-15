"""Runtime settings read from environment variables and .env files.

Lookup order (later wins): repo-root .env, then backend/.env, then real environment variables.
Secrets (LLM_API_KEY) are stored as SecretStr so they never appear in repr() or logs.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.app import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_version: str = __version__

    # LLM (Member 2). Defaults are safe: mock provider, no endpoint, no key.
    llm_provider: Literal["amd_vllm", "gemini", "mock"] = "mock"
    llm_base_url: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_hardware_label: str = ""
    llm_timeout_s: float = 60.0
    llm_max_cases: int = 5

    # API
    frontend_origins: str = "http://localhost:5173"
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
