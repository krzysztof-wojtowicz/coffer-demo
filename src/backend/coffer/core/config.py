from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from coffer.core.db_url import normalize_database_url

ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COFFER_", env_file=ENV_FILE, extra="ignore")

    # contains the DB password: never log; postgres:// URLs (e.g. Neon) are mapped to psycopg 3
    database_url: str = Field(
        default="postgresql+psycopg://coffer:coffer@localhost:5432/coffer", repr=False
    )
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:8000"]
    session_ttl_days: int = 14
    cookie_secure: bool = False
    llm_provider: Literal["ollama", "openai", "gemini", "anthropic", "none"] = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    openai_api_key: str = Field(default="", repr=False)  # secret: never log or return
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"  # any OpenAI-compatible API
    gemini_api_key: str = Field(default="", repr=False)  # secret: never log or return
    gemini_model: str = "gemini-3.8-flash"
    anthropic_api_key: str = Field(default="", repr=False)  # secret: never log or return
    anthropic_model: str = "claude-sonnet-5-5"
    anthropic_base_url: str = "https://api.anthropic.com"
    llm_timeout_s: int = 90
    agent_daily_limit: int = 50  # max agent runs per user per day (local model: no cost)
    agent_max_attempts: int = 2  # 1 call + 1 retry after a failed validation

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
