"""Core: origin policy and CORS, config validation, money serialization, clock, DB URL,
request body limit."""

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from typing import Annotated

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

import coffer.core.clock as clock
from coffer.core.config import Settings, get_settings
from coffer.core.db_url import engine_options, normalize_database_url
from coffer.core.money import MoneyStr, money
from coffer.core.origin import is_allowed_origin
from coffer.main import create_app

# --- Origin policy and CORS ---

LOCAL = "http://localhost:5173"
PROD = "https://coffer.example.com"
PREVIEW = "https://coffer-git-feat-x-team.vercel.app"
EVIL = "https://evil.example"
LOOKALIKES = [
    "https://evil-coffer-x-team.vercel.app",
    "https://coffer-x-team.vercel.app.evil.com",
    "https://COFFER-x-team.vercel.app",
    "https://coffer-x-team.vercel.app:443",
    "http://coffer-x-team.vercel.app",
    "https://coffer-x-teamXvercel.app",
    "https://coffer.example.com.evil.com",
    "https://COFFER.example.com",
    "https://coffer.example.com:8443",
    "https://coffer.example.com/",
    "null",
    "",
]


def _make(**values: object) -> Settings:
    """Settings from explicit values + env only (ignores the developer's .env file)."""
    return Settings(_env_file=None, **values)  # pyright: ignore[reportCallIssue]


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "allowed_origins": [LOCAL, PROD, PREVIEW],
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
def cors_client() -> TestClient:
    return TestClient(_app(_settings()))


def _preflight(
    cors_client: TestClient, origin: str, path: str = "/api/auth/me", method: str = "POST"
):
    return cors_client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        },
    )


@pytest.mark.parametrize("origin", [LOCAL, PROD, PREVIEW])
def test_preflight_allowed_origin(cors_client: TestClient, origin: str) -> None:
    r = _preflight(cors_client, origin)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin
    assert r.headers["access-control-allow-credentials"] == "true"
    assert "Origin" in r.headers["vary"]
    assert "content-type" in r.headers["access-control-allow-headers"].lower()
    assert "PATCH" in r.headers["access-control-allow-methods"]
    assert r.headers["access-control-max-age"] == "600"


def test_preflight_needs_no_login(cors_client: TestClient) -> None:
    # /api/auth/me requires a session; the preflight must not reach auth (no 401/403)
    r = _preflight(cors_client, PROD, method="GET")
    assert r.status_code == 200


@pytest.mark.parametrize("origin", [LOCAL, PREVIEW])
def test_allowed_origin_post_passes_with_cors_headers(cors_client: TestClient, origin: str) -> None:
    r = cors_client.post("/api/_probe", headers={"Origin": origin})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin
    assert r.headers["access-control-allow-credentials"] == "true"
    assert "Origin" in r.headers["vary"]


def test_error_response_has_cors_headers(cors_client: TestClient) -> None:
    r = cors_client.get("/api/auth/me", headers={"Origin": PROD})
    assert r.status_code == 401
    assert r.headers["access-control-allow-origin"] == PROD


def test_no_origin_unchanged(cors_client: TestClient) -> None:
    assert cors_client.get("/api/health").status_code == 200
    r = cors_client.post("/api/_probe")
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers


def test_cors_disabled_by_default_but_origin_check_stays() -> None:
    cors_client = TestClient(_app(_settings(cors_enabled=False)))
    r = cors_client.get("/api/health", headers={"Origin": LOCAL})
    assert "access-control-allow-origin" not in r.headers
    assert cors_client.post("/api/_probe", headers={"Origin": PREVIEW}).status_code == 200
    assert cors_client.post("/api/_probe", headers={"Origin": EVIL}).status_code == 403
    # preflight without CORS: 405 from routing, never 401/403
    assert _preflight(cors_client, LOCAL, path="/api/_probe").status_code == 405
    assert _make().cors_enabled is False


@pytest.mark.parametrize("origin", [LOCAL, PROD, PREVIEW, EVIL, *LOOKALIKES])
def test_cors_and_origin_check_agree(cors_client: TestClient, origin: str) -> None:
    cors_ok = (
        "access-control-allow-origin" in _preflight(cors_client, origin, "/api/_probe").headers
    )
    post_ok = cors_client.post("/api/_probe", headers={"Origin": origin}).status_code == 200
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


@pytest.mark.parametrize("origin", [EVIL, *LOOKALIKES])
def test_disallowed_origin_gets_no_cors_and_403(cors_client: TestClient, origin: str) -> None:
    assert not is_allowed_origin(origin, _settings())
    r = _preflight(cors_client, origin, path="/api/_probe")
    assert "access-control-allow-origin" not in r.headers
    r = cors_client.post("/api/_probe", headers={"Origin": origin})
    assert r.status_code == 403
    assert r.json() == {"detail": "Niedozwolone źródło żądania"}
    assert "access-control-allow-origin" not in r.headers


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_all_unsafe_methods_checked(cors_client: TestClient, method: str) -> None:
    r = cors_client.request(method, "/api/_probe", headers={"Origin": EVIL})
    assert r.status_code == 403


def test_foreign_origin_cannot_log_in_even_with_cors_disabled() -> None:
    c = TestClient(_app(_settings(cors_enabled=False)))
    body = {"email": "a@example.com", "password": "Kot-w-butach-42"}
    assert c.post("/api/auth/login", json=body, headers={"Origin": EVIL}).status_code == 403


@pytest.mark.parametrize(
    "raw",
    ['["https://a.example"', "https://user@a.example", "https://a.example:443", '["*"]'],
)
def test_bad_origins_env_stops_startup(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("COFFER_ALLOWED_ORIGINS", raw)
    with pytest.raises(ValidationError):
        _make()


def test_samesite_only_lax_or_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COFFER_COOKIE_SAMESITE", "none")
    with pytest.raises(ValidationError):
        _make()


# --- Money serialization ---


class In(BaseModel):
    v: Annotated[Decimal, money("Cena")]


class Out(BaseModel):
    v: MoneyStr


def test_money_str_two_decimals_half_up():
    assert Out(v=Decimal("10.5")).model_dump(mode="json")["v"] == "10.50"
    assert Out(v=Decimal("0.005")).model_dump(mode="json")["v"] == "0.01"
    assert Out(v=Decimal("2.345")).model_dump_json() == '{"v":"2.35"}'


@pytest.mark.parametrize("bad", ["NaN", "-1", "1.234", "1000000000000"])
def test_money_rejects(bad):
    with pytest.raises(ValidationError):
        In(v=Decimal(bad))


def test_money_error_names_the_field():
    with pytest.raises(ValidationError, match="Cena nie może być ujemna"):
        In(v=Decimal("-1"))


def test_money_accepts():
    assert In(v=Decimal("10.50")).v == Decimal("10.50")


def test_money_str_huge_value_does_not_overflow():
    assert Out(v=Decimal("1e24") + Decimal("0.005")).model_dump(mode="json")["v"].endswith(".01")


# --- Clock ---


def _freeze(monkeypatch, utc: dt.datetime) -> None:
    class FakeDT(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return utc.astimezone(tz)

    monkeypatch.setattr(clock.dt, "datetime", FakeDT)


def test_today_is_next_day_in_warsaw_after_utc_evening(monkeypatch):
    _freeze(monkeypatch, dt.datetime(2026, 6, 10, 23, 30, tzinfo=dt.UTC))
    assert clock.today() == dt.date(2026, 6, 11)


def test_today_winter_offset(monkeypatch):
    _freeze(monkeypatch, dt.datetime(2026, 1, 10, 22, 59, tzinfo=dt.UTC))
    assert clock.today() == dt.date(2026, 1, 10)
    _freeze(monkeypatch, dt.datetime(2026, 1, 10, 23, 0, tzinfo=dt.UTC))
    assert clock.today() == dt.date(2026, 1, 11)


# --- Database URL ---


NEON = (
    "postgresql://alex:AbC123dEf@ep-cool-darkness-123456.eu-central-1.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (NEON, "postgresql+psycopg://" + NEON.removeprefix("postgresql://")),
        ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        ("POSTGRESQL://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("  postgres://u:p@h/db\n", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://coffer:coffer@localhost:5432/coffer", None),
        ("postgresql+psycopg2://u:p@h/db", None),
        ("sqlite:///x.db", None),
    ],
)
def test_normalize_database_url(raw: str, expected: str | None) -> None:
    assert normalize_database_url(raw) == (expected or raw.strip())


def test_normalize_keeps_ssl_params_and_credentials() -> None:
    url = make_url(normalize_database_url(NEON))
    assert url.drivername == "postgresql+psycopg"
    assert url.username == "alex"
    assert url.password == "AbC123dEf"
    assert url.database == "neondb"
    assert url.query == {"sslmode": "require", "channel_binding": "require"}


def test_normalize_keeps_url_encoded_password() -> None:
    url = make_url(normalize_database_url("postgres://u:p%40ss%2Fw@h/db"))
    assert url.password == "p@ss/w"


def test_settings_normalize_database_url() -> None:
    settings = Settings(_env_file=None, database_url=NEON)  # pyright: ignore[reportCallIssue]
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.database_url.endswith("?sslmode=require&channel_binding=require")


def test_settings_repr_hides_database_url() -> None:
    settings = Settings(_env_file=None, database_url=NEON)  # pyright: ignore[reportCallIssue]
    assert "AbC123dEf" not in repr(settings)


def test_engine_options_direct() -> None:
    options = engine_options()
    assert options["pool_pre_ping"] is True
    assert options["pool_recycle"] > 0
    assert options["pool_size"] + options["max_overflow"] <= 20
    assert "connect_args" not in options


def test_engine_builds_without_connecting() -> None:
    url = normalize_database_url(NEON)
    engine = create_engine(url, **engine_options())  # lazy: no network
    try:
        assert engine.dialect.driver == "psycopg"
        assert engine.url.query["sslmode"] == "require"
    finally:
        engine.dispose()


# --- Request body limit ---


BOUNDARY = "xBOUNDARYx"
HEADERS = {"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"}


def _multipart(size: int) -> bytes:
    head = (
        f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="bank"\r\n\r\nmbank\r\n'
        f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="file"; filename="a.csv"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode()
    return head + b"a" * size + f"\r\n--{BOUNDARY}--\r\n".encode()


def test_oversized_content_length_rejected_413(auth_client: TestClient) -> None:
    body = _multipart(get_settings().max_request_bytes + 1)
    response = auth_client.post("/api/imports", content=body, headers=HEADERS)
    assert response.status_code == 413
    assert response.json()["detail"] == "Żądanie jest za duże"


def test_oversized_chunked_body_rejected_413(auth_client: TestClient) -> None:
    body = _multipart(get_settings().max_request_bytes + 1)

    def chunks() -> Iterator[bytes]:  # no Content-Length: Transfer-Encoding: chunked
        for i in range(0, len(body), 64 * 1024):
            yield body[i : i + 64 * 1024]

    response = auth_client.post("/api/imports", content=chunks(), headers=HEADERS)
    assert response.status_code == 413
    assert response.json()["detail"] == "Żądanie jest za duże"


def test_small_body_passes(auth_client: TestClient) -> None:
    response = auth_client.post("/api/imports", content=_multipart(10), headers=HEADERS)
    assert response.status_code != 413
