"""Runtime settings for the API, read from environment variables and .env files.

Lookup order (later wins): repo-root .env, then backend/.env, then real environment variables.
The LLM_* settings (provider, key, model, ...) are NOT here: llm_client.py reads them itself
(llm_client.LLMConfig.from_env), so there is one place for them.
"""

from functools import lru_cache
from pathlib import Path

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
