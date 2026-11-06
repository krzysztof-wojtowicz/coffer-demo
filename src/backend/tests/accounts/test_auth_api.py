from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from coffer.accounts.models import AuthSession, User
from coffer.accounts.tokens import SESSION_COOKIE, hash_token
from coffer.core.config import get_settings

PASSWORD = "Kot-w-butach-42"


def _creds(email: str = "jan@example.com", password: str = PASSWORD) -> dict:
    return {"email": email, "password": password}


def _set_cookie(response) -> str:
    return response.headers["set-cookie"]


# --- rejestracja ---


def test_register_creates_user_and_logs_in(client: TestClient, db: Session) -> None:
    r = client.post("/api/auth/register", json=_creds())
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"id", "email"}
    assert body["email"] == "jan@example.com"
    assert SESSION_COOKIE in client.cookies
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == body
    assert db.scalars(select(User)).one().id == body["id"]


def test_register_cookie_attributes(client: TestClient) -> None:
    r = client.post("/api/auth/register", json=_creds())
    header = _set_cookie(r)
    lower = header.lower()
    assert header.startswith(f"{SESSION_COOKIE}=")
    assert "httponly" in lower
    assert "samesite=lax" in lower
    assert "path=/" in lower
    ttl = get_settings().session_ttl_days * 86400
    assert f"max-age={ttl}" in lower
    assert ("secure" in lower.replace("samesite", "")) == get_settings().cookie_secure


def test_register_stores_only_argon2_hash(client: TestClient, db: Session) -> None:
    client.post("/api/auth/register", json=_creds())
    user = db.scalars(select(User)).one()
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$argon2")
    assert PASSWORD not in user.password_hash


def test_register_stores_only_token_hash(client: TestClient, db: Session) -> None:
    client.post("/api/auth/register", json=_creds())
    token = client.cookies[SESSION_COOKIE]
    row = db.scalars(select(AuthSession)).one()
    assert row.token_hash == hash_token(token)
    assert row.token_hash != token


def test_register_session_ttl(client: TestClient, db: Session) -> None:
    client.post("/api/auth/register", json=_creds())
    row = db.scalars(select(AuthSession)).one()
    expected = datetime.now(UTC) + timedelta(days=get_settings().session_ttl_days)
    assert abs((row.expires_at - expected).total_seconds()) < 120


def test_register_normalizes_email(client: TestClient, db: Session) -> None:
    r = client.post("/api/auth/register", json=_creds(email="  Jan.Kowalski@Example.COM  "))
    assert r.status_code == 201
    assert r.json()["email"] == "jan.kowalski@example.com"
    assert db.scalars(select(User.email)).one() == "jan.kowalski@example.com"


def test_register_duplicate_email_409(client: TestClient) -> None:
    assert client.post("/api/auth/register", json=_creds()).status_code == 201
    other = TestClient(client.app)
    r = other.post("/api/auth/register", json=_creds())
    assert r.status_code == 409
    assert r.json() == {"detail": "Konto z tym adresem e-mail już istnieje"}
    assert SESSION_COOKIE not in other.cookies


def test_register_duplicate_email_case_insensitive(client: TestClient) -> None:
    client.post("/api/auth/register", json=_creds(email="jan@example.com"))
    r = TestClient(client.app).post("/api/auth/register", json=_creds(email=" JAN@example.com "))
    assert r.status_code == 409


@pytest.mark.parametrize(
    "email",
    [
        "",
        "bez-malpy",
        "@example.com",
        "jan@",
        "jan@example",
        "jan @example.com",
        "a@b@c.pl",
        "jan@exa mple.com",
        "a" * 250 + "@x.pl",
    ],
)
def test_register_invalid_email_422(client: TestClient, email: str) -> None:
    r = client.post("/api/auth/register", json=_creds(email=email))
    assert r.status_code == 422


@pytest.mark.parametrize("password", ["", "1234567", "x" * 129])
def test_register_invalid_password_422(client: TestClient, password: str) -> None:
    r = client.post("/api/auth/register", json=_creds(password=password))
    assert r.status_code == 422


@pytest.mark.parametrize("password", ["Kot-w-butach", ("Abcde12345" * 13)[:128]])
def test_register_password_length_boundaries(client: TestClient, password: str) -> None:
    r = client.post("/api/auth/register", json=_creds(password=password))
    assert r.status_code == 201


def test_register_email_length_boundary(client: TestClient) -> None:
    domain = "@" + ".".join(["d" * 60] * 3) + ".eeeeee"
    ok = "a" * 64 + domain
    assert len(ok) == 254
    assert client.post("/api/auth/register", json=_creds(email=ok)).status_code == 201
    too_long = ok + "e"
    r = TestClient(client.app).post("/api/auth/register", json=_creds(email=too_long))
    assert r.status_code == 422


@pytest.mark.parametrize("payload", [{}, {"email": "a@b.pl"}, {"password": PASSWORD}])
def test_register_missing_fields_422(client: TestClient, payload: dict) -> None:
    assert client.post("/api/auth/register", json=payload).status_code == 422


def test_register_invalid_creates_no_user(client: TestClient, db: Session) -> None:
    client.post("/api/auth/register", json=_creds(password="krotki"))
    assert db.scalars(select(User)).all() == []


# --- logowanie ---


def test_login_success(client: TestClient, make_user) -> None:
    user = make_user(email="jan@example.com", password=PASSWORD)
    r = client.post("/api/auth/login", json=_creds())
    assert r.status_code == 200
    assert r.json() == {"id": user.id, "email": "jan@example.com"}
    assert SESSION_COOKIE in client.cookies
    header = _set_cookie(r).lower()
    assert "httponly" in header
    assert "samesite=lax" in header
    assert f"max-age={get_settings().session_ttl_days * 86400}" in header
    assert client.get("/api/auth/me").json() == {"id": user.id, "email": "jan@example.com"}


def test_login_email_normalized(client: TestClient, make_user) -> None:
    make_user(email="jan@example.com", password=PASSWORD)
    r = client.post("/api/auth/login", json=_creds(email="  JAN@Example.com "))
    assert r.status_code == 200


def test_login_wrong_and_unknown_same_message(client: TestClient, make_user) -> None:
    make_user(email="jan@example.com", password=PASSWORD)
    wrong = client.post("/api/auth/login", json=_creds(password="zlehaslo12345"))
    unknown = client.post("/api/auth/login", json=_creds(email="nikt@example.com"))
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Nieprawidłowy e-mail lub hasło"}
    assert SESSION_COOKIE not in client.cookies


def test_login_password_is_case_sensitive(client: TestClient, make_user) -> None:
    make_user(email="jan@example.com", password="Kot-W-Butach-42")
    r = client.post("/api/auth/login", json=_creds(password="kot-w-butach-42"))
    assert r.status_code == 401


@pytest.mark.parametrize("payload", [{}, {"email": "jan@example.com"}, {"password": PASSWORD}])
def test_login_missing_fields_422(client: TestClient, payload: dict) -> None:
    assert client.post("/api/auth/login", json=payload).status_code == 422


def test_login_creates_independent_sessions(client: TestClient, make_user, db: Session) -> None:
    make_user(email="jan@example.com", password=PASSWORD)
    other = TestClient(client.app)
    client.post("/api/auth/login", json=_creds())
    other.post("/api/auth/login", json=_creds())
    assert client.cookies[SESSION_COOKIE] != other.cookies[SESSION_COOKIE]
    assert len(db.scalars(select(AuthSession)).all()) == 2
    assert client.get("/api/auth/me").status_code == 200
    assert other.get("/api/auth/me").status_code == 200


def test_login_isolates_users(client: TestClient, make_user) -> None:
    a = make_user(email="a@example.com", password=PASSWORD)
    b = make_user(email="b@example.com", password="innehaslo123")
    client.post("/api/auth/login", json=_creds(email="b@example.com", password="innehaslo123"))
    assert client.get("/api/auth/me").json()["id"] == b.id != a.id


# --- /me ---


def test_me_without_session_401(client: TestClient) -> None:
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json() == {"detail": "Wymagane logowanie"}


def test_me_with_garbage_cookie_401(client: TestClient) -> None:
    client.cookies.set(SESSION_COOKIE, "nieistniejacy-token")
    assert client.get("/api/auth/me").status_code == 401


def test_me_expired_session_401(client: TestClient, db: Session) -> None:
    client.post("/api/auth/register", json=_creds())
    db.execute(update(AuthSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    db.commit()
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json() == {"detail": "Wymagane logowanie"}


# --- wylogowanie ---


def test_logout_invalidates_session(client: TestClient, db: Session) -> None:
    client.post("/api/auth/register", json=_creds())
    token = client.cookies[SESSION_COOKIE]
    r = client.post("/api/auth/logout")
    assert r.status_code == 204
    assert r.content == b""
    assert db.scalars(select(AuthSession)).all() == []
    # stary token po wylogowaniu nie działa
    replay = TestClient(client.app)
    replay.cookies.set(SESSION_COOKIE, token)
    assert replay.get("/api/auth/me").status_code == 401


def test_logout_clears_cookie(client: TestClient) -> None:
    client.post("/api/auth/register", json=_creds())
    r = client.post("/api/auth/logout")
    header = _set_cookie(r).lower()
    assert header.startswith(f"{SESSION_COOKIE}=")
    assert "max-age=0" in header or "expires=" in header
    assert SESSION_COOKIE not in client.cookies
    assert client.get("/api/auth/me").status_code == 401


def test_logout_without_session_204(client: TestClient) -> None:
    assert client.post("/api/auth/logout").status_code == 204


def test_logout_with_unknown_token_204(client: TestClient) -> None:
    client.cookies.set(SESSION_COOKIE, "nieistniejacy-token")
    assert client.post("/api/auth/logout").status_code == 204


def test_logout_only_current_session(client: TestClient, make_user, db: Session) -> None:
    make_user(email="jan@example.com", password=PASSWORD)
    other = TestClient(client.app)
    client.post("/api/auth/login", json=_creds())
    other.post("/api/auth/login", json=_creds())
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    assert other.get("/api/auth/me").status_code == 200
    assert len(db.scalars(select(AuthSession)).all()) == 1


def test_logout_does_not_touch_other_users(
    client: TestClient, other_auth_client: TestClient
) -> None:
    client.post("/api/auth/register", json=_creds())
    client.post("/api/auth/logout")
    assert other_auth_client.get("/api/auth/me").status_code == 200


def test_login_again_after_logout(client: TestClient) -> None:
    client.post("/api/auth/register", json=_creds())
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json=_creds()).status_code == 200
    assert client.get("/api/auth/me").status_code == 200


# --- CSRF ---


def test_login_foreign_origin_403(client: TestClient, make_user) -> None:
    make_user(email="jan@example.com", password=PASSWORD)
    r = client.post("/api/auth/login", json=_creds(), headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert SESSION_COOKIE not in client.cookies


def test_login_allowed_origin_ok(client: TestClient, make_user) -> None:
    make_user(email="jan@example.com", password=PASSWORD)
    origin = get_settings().allowed_origins[0]
    r = client.post("/api/auth/login", json=_creds(), headers={"Origin": origin})
    assert r.status_code == 200
