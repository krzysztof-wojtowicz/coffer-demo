"""Tester: origin policy (CSRF Origin check + CORS) and its config validation.

Written from the task contract, not from the implementation.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from coffer.core.config import Settings
from coffer.core.origin import is_allowed_origin
from coffer.main import create_app

LIST_ORIGIN = "https://cofferai.vercel.app"
REGEX = r"https://coffer-[a-z0-9-]+-team\.vercel\.app"
PREVIEW = "https://coffer-git-main-team.vercel.app"


def _make(**values: object) -> Settings:
    return Settings(_env_file=None, **values)  # pyright: ignore[reportCallIssue]


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "allowed_origins": [LIST_ORIGIN],
        "allowed_origin_regex": REGEX,
        "cors_enabled": True,
    }
    return _make(**(base | overrides))


def _app(settings: Settings) -> FastAPI:
    app = create_app(settings)

    @app.post("/api/_probe")
    def probe() -> dict[str, str]:
        return {"ok": "1"}

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_app(_settings()))


def _preflight(c: TestClient, origin: str, path: str = "/api/_probe", method: str = "POST"):
    return c.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        },
    )


@pytest.mark.parametrize("origin", [LIST_ORIGIN, PREVIEW])
def test_allowed_preflight_and_post(client: TestClient, origin: str) -> None:
    r = _preflight(client, origin)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin
    assert r.headers["access-control-allow-credentials"] == "true"
    assert "POST" in r.headers["access-control-allow-methods"]
    assert r.headers.get("access-control-allow-origin") != "*"
    p = client.post("/api/_probe", headers={"Origin": origin})
    assert p.status_code == 200
    assert p.headers["access-control-allow-origin"] == origin
    assert "origin" in p.headers.get("vary", "").lower()


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil-coffer-x-team.vercel.app",
        "https://coffer-x-team.vercel.app.evil.com",
        "https://COFFER-x-team.vercel.app",
        "https://coffer-x-team.vercel.app:443",
        "https://coffer-x-team.vercel.app:8443",
        "http://coffer-x-team.vercel.app",
        "https://cofferai.vercel.app.evil.com",
        "https://CofferAI.vercel.app",
        "https://cofferai.vercel.app:8443",
        "https://cofferai.vercel.app/",
        "null",
        "",
    ],
)
def test_lookalike_origins_rejected(client: TestClient, origin: str) -> None:
    assert not is_allowed_origin(origin, _settings())
    assert "access-control-allow-origin" not in _preflight(client, origin).headers
    r = client.post("/api/_probe", headers={"Origin": origin})
    assert r.status_code == 403
    assert r.json() == {"detail": "Niedozwolone źródło żądania"}
    assert "access-control-allow-origin" not in r.headers


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_all_unsafe_methods_checked(client: TestClient, method: str) -> None:
    r = client.request(method, "/api/_probe", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_foreign_origin_cannot_log_in_even_with_cors_disabled() -> None:
    c = TestClient(_app(_settings(cors_enabled=False)))
    body = {"email": "a@example.com", "password": "Kot-w-butach-42"}
    r = c.post("/api/auth/login", json=body, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_preflight_to_protected_route_never_401(client: TestClient) -> None:
    for path in ("/api/auth/me", "/api/auth/account", "/api/auth/password"):
        r = _preflight(client, LIST_ORIGIN, path=path, method="DELETE")
        assert r.status_code == 200, path


def test_401_carries_cors_headers(client: TestClient) -> None:
    r = client.get("/api/auth/me", headers={"Origin": PREVIEW})
    assert r.status_code == 401
    assert r.headers["access-control-allow-origin"] == PREVIEW


# --- config validation at startup ---


@pytest.mark.parametrize(
    "raw",
    [
        '["https://cofferai.vercel.app"]',
        "https://cofferai.vercel.app",
        " https://cofferai.vercel.app , ",
    ],
)
def test_origins_env_formats(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("COFFER_ALLOWED_ORIGINS", raw)
    assert _make().allowed_origins == [LIST_ORIGIN]


@pytest.mark.parametrize(
    "raw",
    [
        '["https://cofferai.vercel.app/"]',
        '["https://cofferai.vercel.app"',
        '["*"]',
        "*",
        "https://user@a.example",
    ],
)
def test_bad_origins_env_stops_startup(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("COFFER_ALLOWED_ORIGINS", raw)
    with pytest.raises(ValidationError):
        _make()


@pytest.mark.parametrize("bad", [".*", "^.*$", "(https://.*)", "https?://.*"])
def test_catch_all_regex_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        _make(allowed_origin_regex=bad)


@pytest.mark.parametrize("bad", ["https://.*", r"https://coffer\.app|.*", "http://localhost.*"])
def test_catch_all_after_literal_prefix_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        _make(allowed_origin_regex=bad)


def test_origin_with_default_port_rejected() -> None:
    with pytest.raises(ValidationError):
        _make(allowed_origins=["https://a.example:443"])


def test_samesite_none_without_secure_fails_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COFFER_COOKIE_SAMESITE", "none")
    monkeypatch.setenv("COFFER_COOKIE_SECURE", "false")
    with pytest.raises(ValidationError, match="COFFER_COOKIE_SECURE"):
        _make()
    monkeypatch.setenv("COFFER_COOKIE_SAMESITE", "Lax")
    with pytest.raises(ValidationError):
        _make()  # only lax/strict/none, exactly
