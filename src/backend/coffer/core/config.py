import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from coffer.core.db_url import normalize_database_url

ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COFFER_", env_file=ENV_FILE, extra="ignore")

    # contains the DB password: never log; postgres:// URLs are mapped to psycopg 3
    database_url: str = Field(
        default="postgresql+psycopg://coffer:coffer@localhost:5432/coffer", repr=False
    )
    # Single source of truth for trusted browser origins: used by the Origin (CSRF) check and,
    # when cors_enabled, by CORS. Env: JSON list or comma-separated list.
    allowed_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:8000",
    ]
    # CORS is only needed when the browser calls the API directly from another origin.
    cors_enabled: bool = False
    session_ttl_days: int = 14
    # business "today" (matches the users' frontend); IANA name
    timezone: str = "Europe/Warsaw"
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict"] = "lax"
    # Reverse proxies in front of the API that append to X-Forwarded-For (auth rate limiting).
    # 0 = use the socket peer (local dev); e.g. one reverse proxy = 1.
    trusted_proxy_hops: int = Field(default=0, ge=0)
    # Max concurrent Argon2 hash/verify calls (memory bound; legacy hashes use 64 MiB each).
    password_hash_concurrency: int = Field(default=2, ge=1)
    # Max request body (413 above it); a bit over the 1 MB import cap plus multipart overhead.
    max_request_bytes: int = Field(default=2 * 1024 * 1024, gt=0)
    price_refresh_minutes: int = Field(default=0, ge=0, le=1440)

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: object) -> object:
        return _split_list(value)

    @field_validator("allowed_origins")
    @classmethod
    def _validate_origins(cls, value: list[str]) -> list[str]:
        for origin in value:
            _check_origin(origin)
        return value


_DEFAULT_PORTS = {"http": 80, "https": 443}


def _split_list(value: object) -> object:
    """Env value as JSON list or comma-separated text."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text.startswith("["):
        return json.loads(text)
    return [item.strip() for item in text.split(",") if item.strip()]


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
            "in lowercase, without default port, path or trailing '/', e.g. https://coffer.example.com"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
