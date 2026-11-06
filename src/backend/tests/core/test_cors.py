from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from pydantic import ValidationError

from coffer.agent.sse import SSE_HEADERS
from coffer.core.config import Settings
from coffer.core.origin import is_allowed_origin
from coffer.main import create_app

LOCAL = "http://localhost:5173"
PROD = "https://coffer.example.com"
PREVIEW_REGEX = r"https://coffer-[a-z0-9-]+-team\.vercel\.app"
PREVIEW = "https://coffer-git-feat-x-team.vercel.app"
EVIL = "https://evil.example"
LOOKALIKES = [
    "https://evil-coffer-x-team.vercel.app",
    "https://coffer-x-team.vercel.app.evil.com",
    "http://coffer-x-team.vercel.app",
    "https://coffer-x-teamXvercel.app",
]


def _make(**values: object) -> Settings:
    """Settings from explicit values + env only (ignores the developer's .env file)."""
    return Settings(_env_file=None, **values)  # pyright: ignore[reportCallIssue]


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "allowed_origins": [LOCAL, PROD],
        "allowed_origin_regex": PREVIEW_REGEX,
        "cors_enabled": True,
    }
    return _make(**(base | overrides))


def _app(settings: Settings) -> FastAPI:
    app = create_app(settings)

    @app.post("/api/_probe")
    def probe() -> dict[str, str]:
        return {"ok": "1"}

    @app.get("/api/_sse")
    def sse() -> StreamingResponse:
        def gen() -> Iterator[str]:
            yield "event: done\ndata: {}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_app(_settings()))


def _preflight(client: TestClient, origin: str, path: str = "/api/auth/me", method: str = "POST"):
    return client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        },
    )


@pytest.mark.parametrize("origin", [LOCAL, PROD, PREVIEW])
def test_preflight_allowed_origin(client: TestClient, origin: str) -> None:
    r = _preflight(client, origin)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin
    assert r.headers["access-control-allow-credentials"] == "true"
    assert "Origin" in r.headers["vary"]
    assert "content-type" in r.headers["access-control-allow-headers"].lower()
    assert "PATCH" in r.headers["access-control-allow-methods"]
    assert r.headers["access-control-max-age"] == "600"


def test_preflight_needs_no_login(client: TestClient) -> None:
    # /api/auth/me requires a session; the preflight must not reach auth (no 401/403)
    r = _preflight(client, PROD, method="GET")
    assert r.status_code == 200


@pytest.mark.parametrize("origin", [EVIL, *LOOKALIKES])
def test_disallowed_origin_gets_no_cors_and_403(client: TestClient, origin: str) -> None:
    r = _preflight(client, origin, path="/api/_probe")
    assert "access-control-allow-origin" not in r.headers
    r = client.post("/api/_probe", headers={"Origin": origin})
    assert r.status_code == 403
    assert "access-control-allow-origin" not in r.headers


@pytest.mark.parametrize("origin", [LOCAL, PREVIEW])
def test_allowed_origin_post_passes_with_cors_headers(client: TestClient, origin: str) -> None:
    r = client.post("/api/_probe", headers={"Origin": origin})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin
    assert r.headers["access-control-allow-credentials"] == "true"
    assert "Origin" in r.headers["vary"]


def test_error_response_has_cors_headers(client: TestClient) -> None:
    r = client.get("/api/auth/me", headers={"Origin": PROD})
    assert r.status_code == 401
    assert r.headers["access-control-allow-origin"] == PROD


def test_no_origin_unchanged(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 200
    r = client.post("/api/_probe")
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers


def test_sse_stream_has_cors_headers(client: TestClient) -> None:
    r = client.get("/api/_sse", headers={"Origin": PREVIEW, "Accept": "text/event-stream"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == PREVIEW
    assert r.headers["cache-control"] == "no-cache"
    assert "event: done" in r.text


def test_cors_disabled_by_default_but_origin_check_stays() -> None:
    client = TestClient(_app(_settings(cors_enabled=False)))
    r = client.get("/api/health", headers={"Origin": LOCAL})
    assert "access-control-allow-origin" not in r.headers
    assert client.post("/api/_probe", headers={"Origin": PREVIEW}).status_code == 200
    assert client.post("/api/_probe", headers={"Origin": EVIL}).status_code == 403
    # preflight without CORS: 405 from routing, never 401/403
    assert _preflight(client, LOCAL, path="/api/_probe").status_code == 405
    assert _make().cors_enabled is False


@pytest.mark.parametrize("origin", [LOCAL, PROD, PREVIEW, EVIL, *LOOKALIKES])
def test_cors_and_origin_check_agree(client: TestClient, origin: str) -> None:
    cors_ok = "access-control-allow-origin" in _preflight(client, origin, "/api/_probe").headers
    post_ok = client.post("/api/_probe", headers={"Origin": origin}).status_code == 200
    assert cors_ok == post_ok == is_allowed_origin(origin, _settings())


@pytest.mark.parametrize(
    "raw",
    ['["http://localhost:5173","https://a.example"]', "http://localhost:5173, https://a.example"],
)
def test_origins_env_json_or_csv(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("COFFER_ALLOWED_ORIGINS", raw)
    assert _make().allowed_origins == [
        "http://localhost:5173",
        "https://a.example",
    ]


@pytest.mark.parametrize(
    "bad",
    [
        "https://a.example/",
        "a.example",
        "*",
        "https://a.example/app",
        "ftp://a.example",
        "https://A.example",
    ],
)
def test_invalid_origin_rejected(bad: str) -> None:
    with pytest.raises(ValidationError, match="COFFER_ALLOWED_ORIGINS"):
        _make(allowed_origins=[bad])


@pytest.mark.parametrize("bad", [".*", "https://(", "coffer\\.vercel\\.app"])
def test_invalid_origin_regex_rejected(bad: str) -> None:
    with pytest.raises(ValidationError, match="COFFER_ALLOWED_ORIGIN_REGEX"):
        _make(allowed_origin_regex=bad)


def test_samesite_none_requires_secure() -> None:
    with pytest.raises(ValidationError, match="COFFER_COOKIE_SECURE"):
        _make(cookie_samesite="none", cookie_secure=False)
    s = _make(cookie_samesite="none", cookie_secure=True)
    assert s.cookie_samesite == "none"
