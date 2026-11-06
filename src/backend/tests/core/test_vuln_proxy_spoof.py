"""Exploit: spoofed X-Forwarded-For bypasses the per-IP login limit in the production setup.

Production = uvicorn flags from the Dockerfile CMD + COFFER_TRUSTED_PROXY_HOPS from render.yaml.
Attacker calls onrender.com directly (bypassing Vercel), sends its own X-Forwarded-For; Render's
proxy (private peer address) appends the real client IP. Each attempt uses a fresh e-mail, so only
the per-IP limit (30 failures / 15 min) can stop the credential stuffing.
"""

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from coffer.accounts.ratelimit import LOGIN_FAILS_PER_IP, limiter
from coffer.core.config import get_settings
from coffer.main import app

REPO = Path(__file__).resolve().parents[4]
ATTACKER = "203.0.113.7"
RENDER_PROXY_PEER = ("10.0.0.1", 40000)


def _forwarded_allow_ips() -> str:
    cmd = (REPO / "src/backend/Dockerfile").read_text()
    match = re.search(r"--forwarded-allow-ips[= ]'?([^'\s\"]+)'?", cmd)
    return match.group(1) if match else "127.0.0.1"


def _render_proxy_hops() -> int:
    blueprint = (REPO / "render.yaml").read_text()
    match = re.search(r"COFFER_TRUSTED_PROXY_HOPS\s*\n\s*value:\s*\"?(\d+)", blueprint)
    return int(match.group(1)) if match else 0


@pytest.fixture
def prod_like(test_engine, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("COFFER_TRUSTED_PROXY_HOPS", str(_render_proxy_hops()))
    get_settings.cache_clear()
    limiter.reset()
    proxied = ProxyHeadersMiddleware(app, trusted_hosts=_forwarded_allow_ips())  # pyright: ignore[reportArgumentType]
    yield TestClient(proxied, client=RENDER_PROXY_PEER)  # pyright: ignore[reportArgumentType]
    limiter.reset()
    get_settings.cache_clear()


@pytest.mark.xfail(
    strict=True,
    reason="Known, not fixed: needs the real Vercel->Render X-Forwarded-For layout from "
    "Render logs (release-checklist §6) or blocking direct onrender.com access. "
    "Remove xfail with the fix.",
)
def test_spoofed_forwarded_for_does_not_bypass_ip_limit(prod_like: TestClient) -> None:
    limit = LOGIN_FAILS_PER_IP[0]
    statuses = [
        prod_like.post(
            "/api/auth/login",
            json={"email": f"victim{i}@example.com", "password": "wrong-password-123"},
            headers={"X-Forwarded-For": f"198.51.100.{i % 250}, {ATTACKER}"},
        ).status_code
        for i in range(limit + 1)
    ]
    assert statuses[:limit] == [401] * limit
    assert statuses[limit] == 429
