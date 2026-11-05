from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COFFER_", env_file=ENV_FILE, extra="ignore")

    database_url: str = "postgresql+psycopg://coffer:coffer@localhost:5432/coffer"
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:8000"]
    session_ttl_days: int = 14
    cookie_secure: bool = False
    llm_provider: Literal["ollama", "none"] = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    llm_timeout_s: int = 90
    agent_daily_limit: int = 50  # max agent runs per user per day (local model: no cost)
    agent_max_attempts: int = 2  # 1 call + 1 retry after a failed validation


@lru_cache
def get_settings() -> Settings:
    return Settings()
