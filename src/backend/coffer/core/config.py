import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from coffer.core.db_url import normalize_database_url

ENV_FILE = Path(__file__).resolve().parents[4] / ".env"

# Providers allowed in COFFER_LLM_FALLBACKS entries ("provider:model").
LLM_CHAIN_PROVIDERS = ("ollama", "openai", "gemini", "anthropic")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COFFER_", env_file=ENV_FILE, extra="ignore")

    # contains the DB password: never log; postgres:// URLs (e.g. Neon) are mapped to psycopg 3
    database_url: str = Field(
        default="postgresql+psycopg://coffer:coffer@localhost:5432/coffer", repr=False
    )
    # Single source of truth for trusted browser origins: used by the Origin (CSRF) check and,
    # when cors_enabled, by CORS. Env: JSON list or comma-separated list.
    allowed_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:8000",
    ]
    # Optional extra origins (e.g. Vercel previews), matched with re.fullmatch; same dual use.
    allowed_origin_regex: str | None = None
    # CORS is only needed when the browser calls the API directly from another origin
    # (production goes through the Vercel rewrite, i.e. same origin).
    cors_enabled: bool = False
    session_ttl_days: int = 14
    # business "today" (matches the users' frontend); IANA name
    timezone: str = "Europe/Warsaw"
    cookie_secure: bool = False
    # "none" is only needed for cross-site cookies (direct cross-site calls); requires Secure
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    # Reverse proxies in front of the API that append to X-Forwarded-For (auth rate limiting).
    # 0 = use the socket peer (local dev); Vercel rewrite -> Render = 2.
    trusted_proxy_hops: int = Field(default=0, ge=0)
    # Max concurrent Argon2 hash/verify calls (memory bound; legacy hashes use 64 MiB each).
    password_hash_concurrency: int = Field(default=2, ge=1)
    # Max request body (413 above it); a bit over the 1 MB import cap plus multipart overhead.
    max_request_bytes: int = Field(default=2 * 1024 * 1024, gt=0)
    llm_provider: Literal["ollama", "openai", "gemini", "anthropic", "none"] = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    # Only for a remote/hosted Ollama (e.g. https://ollama.com); sent as "Authorization: Bearer"
    ollama_api_key: str = Field(default="", repr=False)  # secret: never log or return
    openai_api_key: str = Field(default="", repr=False)  # secret: never log or return
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"  # any OpenAI-compatible API
    gemini_api_key: str = Field(default="", repr=False)  # secret: never log or return
    gemini_model: str = "gemini-3.5-flash-lite"  # stable; 3.8-flash is often overloaded (503)
    anthropic_api_key: str = Field(default="", repr=False)  # secret: never log or return
    anthropic_model: str = "claude-sonnet-5-5"
    anthropic_base_url: str = "https://api.anthropic.com"
    llm_timeout_s: int = 90  # total budget per model call, retries included
    # Whole investment-advisor run (all tool-calling steps); below the 120 s Vercel proxy limit
    advisor_timeout_s: int = Field(default=60, gt=0, lt=110)
    # Fallback chain tried after the primary (llm_provider + its *_model) on LLMUnavailable.
    # Env: comma list or JSON list of "provider:model", e.g.
    # "gemini:gemini-3.8-flash,anthropic:claude-haiku-5-5"; an entry equal to the primary
    # is skipped. Keys/URLs come from the provider's own settings.
    llm_fallbacks: Annotated[list[str], NoDecode] = []
    agent_daily_limit: int = 50  # max agent runs per user per day (local model: no cost)
    agent_max_attempts: int = 2  # 1 call + 1 retry after a failed validation

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                return json.loads(text)
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    @field_validator("llm_fallbacks", mode="before")
    @classmethod
    def _parse_llm_fallbacks(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                return json.loads(text)
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    @field_validator("llm_fallbacks")
    @classmethod
    def _validate_llm_fallbacks(cls, value: list[str]) -> list[str]:
        for entry in value:
            provider, _, model = entry.partition(":")
            if provider not in LLM_CHAIN_PROVIDERS or not model.strip():
                raise ValueError(
                    f"COFFER_LLM_FALLBACKS: invalid entry {entry!r}; expected provider:model "
                    f"with provider in {', '.join(LLM_CHAIN_PROVIDERS)}"
                )
        return value

    @field_validator("allowed_origins")
    @classmethod
    def _validate_origins(cls, value: list[str]) -> list[str]:
        for origin in value:
            _check_origin(origin)
        return value

    @field_validator("allowed_origin_regex")
    @classmethod
    def _validate_origin_regex(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        pattern = value.strip().removeprefix("^").removesuffix("$")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"COFFER_ALLOWED_ORIGIN_REGEX: invalid regex ({exc})") from None
        if not _SAFE_ORIGIN_REGEX.fullmatch(pattern):
            raise ValueError(
                "COFFER_ALLOWED_ORIGIN_REGEX: unsafe or unsupported pattern; expected "
                r"https://<literal start>[a-z0-9-]+...\.<literal>\.<tld> (e.g. "
                r"https://cofferai-[a-z0-9-]+-team\.vercel\.app) or http://localhost(:\d+)?; "
                "no '.', '|', groups or wildcards in the host, optional ^ and $"
            )
        return pattern

    @model_validator(mode="after")
    def _validate_cookie(self) -> "Settings":
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COFFER_COOKIE_SAMESITE=none requires COFFER_COOKIE_SECURE=true")
        return self


_DEFAULT_PORTS = {"http": 80, "https": 443}

# Grammar for COFFER_ALLOWED_ORIGIN_REGEX (matched against the pattern text itself).
# HTTPS host: a literal first character, then literals / [a-z0-9-] classes with quantifiers
# (no '.', '|', groups, wildcards), then at least two literal labels (\.vercel\.app), so a
# match can never leave the given registrable domain. Plain http only for localhost.
_RX_CLASS = r"\[(?:a-z|0-9|\\d|-)+\]"
_RX_QUANT = r"(?:[+*?]|\{\d+(?:,\d*)?\})?"
_RX_ATOM = rf"(?:[a-z0-9-]|{_RX_CLASS}{_RX_QUANT}|\\d{_RX_QUANT})"
_RX_PORT = r"(?::\d+|:\\d\+|\(\?::\\d\+\)\?|\(:\\d\+\)\?)?"
_SAFE_ORIGIN_REGEX = re.compile(
    rf"https://[a-z0-9]{_RX_ATOM}*(?:\\\.[a-z0-9-]+){{2,}}{_RX_PORT}"
    rf"|http://(?:localhost|127\\\.0\\\.0\\\.1){_RX_PORT}"
)


def _check_origin(origin: str) -> None:
    """An origin is scheme://host[:port], exactly as browsers send it in the Origin header."""
    parts = urlsplit(origin)
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or origin != f"{parts.scheme}://{parts.netloc}"
        or "@" in parts.netloc
        or origin != origin.lower()  # browsers send a lowercase origin; mixed case never matches
        or parts.port == _DEFAULT_PORTS[parts.scheme]  # browsers omit the default port
    ):
        raise ValueError(
            f"COFFER_ALLOWED_ORIGINS: invalid origin {origin!r}; expected scheme://host[:port] "
            "in lowercase, without default port, path or trailing '/', e.g. https://coffer.vercel.app"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
