import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from coffer.accounts import ratelimit, service
from coffer.accounts.models import AuthSession, User
from coffer.accounts.policy import common_passwords, password_problems
from coffer.accounts.ratelimit import SlidingWindowLimiter, client_ip
from coffer.accounts.tokens import SESSION_COOKIE
from coffer.core.config import get_settings
from coffer.main import app
from coffer.portfolio.models import Holding
from coffer.transactions.models import Transaction

PASSWORD = "Kot-w-butach-42"
NEW_PASSWORD = "Pies-w-kaloszach-7"
FRONT_LIST = Path(__file__).resolve().parents[3] / "frontend/src/features/auth/commonPasswords.json"


def _creds(email: str = "jan@example.com", password: str = PASSWORD) -> dict:
    return {"email": email, "password": password}


def _logged_in(make_user, email: str = "jan@example.com") -> tuple[TestClient, User]:
    user = make_user(email=email, password=PASSWORD)
    c = TestClient(app)
    assert c.post("/api/auth/login", json=_creds(email=email)).status_code == 200
    return c, user


# --- hashing ---


def test_hash_uses_explicit_argon2id_params() -> None:
    h = service.hash_password(PASSWORD)
    assert h.startswith("$argon2id$v=19$m=19456,t=2,p=1$")


def test_hash_concurrency_is_capped() -> None:
    assert get_settings().password_hash_concurrency == 2
    assert service.HASH_CONCURRENCY == 2
    for _ in range(2):
        assert service._hash_slots.acquire(blocking=False)
    try:
        assert not service._hash_slots.acquire(blocking=False)
    finally:
        for _ in range(2):
            service._hash_slots.release()


def test_login_rehashes_old_params(client: TestClient, make_user, db: Session) -> None:
    # conftest hashes with argon2-cffi defaults (m=65536,t=3,p=4): an "old" hash
    user = make_user(email="jan@example.com", password=PASSWORD)
    old = user.password_hash
    assert "m=65536" in old
    assert client.post("/api/auth/login", json=_creds()).status_code == 200
    db.expire_all()
    stored = db.get(User, user.id)
    assert stored.password_hash != old
    assert "m=19456,t=2,p=1" in stored.password_hash
    assert stored.last_login_at is not None
    # the upgraded hash still works
    assert TestClient(app).post("/api/auth/login", json=_creds()).status_code == 200


def test_failed_login_does_not_rehash(client: TestClient, make_user, db: Session) -> None:
    user = make_user(email="jan@example.com", password=PASSWORD)
    client.post("/api/auth/login", json=_creds(password="zle-haslo-123"))
    db.expire_all()
    assert db.get(User, user.id).password_hash == user.password_hash


def test_unknown_email_verifies_dummy_hash(db: Session, monkeypatch) -> None:
    calls: list[str] = []
    real = service.verify_password

    def spy(h: str, p: str) -> bool:
        calls.append(h)
        return real(h, p)

    monkeypatch.setattr(service, "verify_password", spy)
    assert service.authenticate(db, "nikt@example.com", PASSWORD) is None
    assert calls == [service._DUMMY_HASH]


def test_overlong_password_rejected_before_hashing(client: TestClient) -> None:
    r = client.post("/api/auth/login", json=_creds(password="x" * 10_000))
    assert r.status_code == 422


# --- e-mail ---


def test_login_case_insensitive_for_legacy_mixed_case_row(client: TestClient, db: Session) -> None:
    db.add(User(email="Jan@Example.com", password_hash=PasswordHasher().hash(PASSWORD)))
    db.commit()
    assert client.post("/api/auth/login", json=_creds(email="jan@example.com")).status_code == 200
    r = TestClient(app).post("/api/auth/register", json=_creds(email="JAN@example.com"))
    assert r.status_code == 409


def test_db_unique_index_is_case_insensitive(db: Session) -> None:
    db.add(User(email="jan@example.com", password_hash="x"))
    db.commit()
    db.add(User(email="JAN@example.com", password_hash="x"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_service_register_normalizes(db: Session) -> None:
    user = service.register(db, "  Ola@Example.PL ", PASSWORD)
    assert user.email == "ola@example.pl"
    with pytest.raises(service.EmailTaken):
        service.register(db, "OLA@example.pl", PASSWORD)


# --- password policy ---


@pytest.mark.parametrize(
    ("password", "fragment"),
    [
        ("Krotkie-1", "co najmniej 12"),
        ("aaaaaaaaaaaaaaaa", "różnych znaków"),
        ("jan.kowalski@example.com", "adres e-mail"),
        ("Jan.Kowalski", "adres e-mail"),
        ("Password1234", "popularne"),
        ("QWERTY123456", "popularne"),
    ],
)
def test_register_policy_violations(client: TestClient, password: str, fragment: str) -> None:
    r = client.post(
        "/api/auth/register", json=_creds(email="jan.kowalski@example.com", password=password)
    )
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)
    assert fragment in r.json()["detail"]
    assert SESSION_COOKIE not in client.cookies


def test_policy_lists_all_problems() -> None:
    problems = password_problems("aaaa", "a@b.pl")
    assert len(problems) == 2


def test_policy_whitespace_set_matches_python_isspace() -> None:
    from coffer.accounts.policy import WHITESPACE

    assert set(WHITESPACE) == {chr(i) for i in range(0x110000) if chr(i).isspace()}
    assert password_problems("jan.kowalski\ufeff", "jan.kowalski@example.com") == []


def test_validation_errors_do_not_echo_password(client: TestClient) -> None:
    secret = "tajne-haslo-" + "x" * 200
    r = client.post("/api/auth/login", json={"password": secret})
    assert r.status_code == 422
    assert secret not in r.text
    assert all(
        e["msg"] in ("Pole jest wymagane", "Niepoprawna wartość") for e in r.json()["detail"]
    )
    r = client.post("/api/auth/login", json=_creds(password=secret))
    assert r.status_code == 422
    assert secret not in r.text and "najwyżej 128" in r.json()["detail"]


def test_policy_accepts_good_password() -> None:
    assert password_problems(PASSWORD, "jan@example.com") == []


def test_common_password_lists_in_sync() -> None:
    front = json.loads(FRONT_LIST.read_text(encoding="utf-8"))
    assert set(front) == set(common_passwords())


# --- rate limiting ---


def test_login_rate_limit_per_email(client: TestClient, make_user) -> None:
    make_user(email="jan@example.com", password=PASSWORD)
    limit, window = ratelimit.LOGIN_FAILS_PER_EMAIL
    for _ in range(limit):
        r = client.post("/api/auth/login", json=_creds(password="zle-haslo-123"))
        assert r.status_code == 401
    r = client.post("/api/auth/login", json=_creds())  # even the right password
    assert r.status_code == 429
    assert "Zbyt wiele prób" in r.json()["detail"]
    assert 0 < int(r.headers["Retry-After"]) <= window
    # another account from the same IP is not locked yet
    make_user(email="ola@example.com", password=PASSWORD)
    assert client.post("/api/auth/login", json=_creds(email="ola@example.com")).status_code == 200


def test_login_rate_limit_per_ip(client: TestClient) -> None:
    limit, _ = ratelimit.LOGIN_FAILS_PER_IP
    for i in range(limit):
        r = client.post("/api/auth/login", json=_creds(email=f"u{i}@example.com"))
        assert r.status_code == 401
    r = client.post("/api/auth/login", json=_creds(email="new@example.com"))
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_successful_login_resets_email_counter(client: TestClient, make_user) -> None:
    make_user(email="jan@example.com", password=PASSWORD)
    limit, _ = ratelimit.LOGIN_FAILS_PER_EMAIL
    for _ in range(limit - 1):
        client.post("/api/auth/login", json=_creds(password="zle-haslo-123"))
    assert client.post("/api/auth/login", json=_creds()).status_code == 200
    for _ in range(limit - 1):
        client.post("/api/auth/login", json=_creds(password="zle-haslo-123"))
    assert client.post("/api/auth/login", json=_creds()).status_code == 200


def test_register_rate_limit_per_ip(client: TestClient) -> None:
    limit, _ = ratelimit.REGISTER_PER_IP
    for i in range(limit):
        r = TestClient(app).post("/api/auth/register", json=_creds(email=f"u{i}@example.com"))
        assert r.status_code == 201
    r = client.post("/api/auth/register", json=_creds(email="late@example.com"))
    assert r.status_code == 429


def test_sliding_window_expires() -> None:
    now = [0.0]
    lim = SlidingWindowLimiter(clock=lambda: now[0])
    lim.hit("k")
    lim.hit("k")
    assert lim.retry_after("k", 2, 60) == 60
    now[0] = 30.0
    assert lim.retry_after("k", 2, 60) == 30
    now[0] = 60.0
    assert lim.retry_after("k", 2, 60) is None


def _req(headers: dict[str, str], host: str = "10.0.0.1"):
    from starlette.requests import Request

    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw, "client": (host, 1234)})


def test_client_ip_ignores_forwarded_without_trusted_hops(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "trusted_proxy_hops", 0)
    assert client_ip(_req({"X-Forwarded-For": "6.6.6.6"})) == "10.0.0.1"


def test_client_ip_takes_nth_from_right(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "trusted_proxy_hops", 2)
    xff = "6.6.6.6, 1.2.3.4, 76.76.21.1"  # spoofed, real client (Vercel), Vercel (Render)
    assert client_ip(_req({"X-Forwarded-For": xff})) == "1.2.3.4"
    assert client_ip(_req({"X-Forwarded-For": "1.2.3.4"})) == "1.2.3.4"
    assert client_ip(_req({})) == "10.0.0.1"


# --- sessions ---


def test_login_rotates_existing_session(make_user, db: Session) -> None:
    c, _ = _logged_in(make_user)
    first = c.cookies[SESSION_COOKIE]
    assert c.post("/api/auth/login", json=_creds()).status_code == 200
    assert c.cookies[SESSION_COOKIE] != first
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 1
    replay = TestClient(app)
    replay.cookies.set(SESSION_COOKIE, first)
    assert replay.get("/api/auth/me").status_code == 401


def test_new_session_purges_expired(make_user, db: Session) -> None:
    c, user = _logged_in(make_user)
    db.execute(
        update(AuthSession).values(expires_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=1))
    )
    db.commit()
    TestClient(app).post("/api/auth/login", json=_creds())
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 1


@pytest.mark.parametrize("samesite", ["strict", "none"])
def test_cookie_samesite_from_settings(make_user, monkeypatch, samesite: str) -> None:
    monkeypatch.setattr(get_settings(), "cookie_samesite", samesite)
    monkeypatch.setattr(get_settings(), "cookie_secure", True)
    make_user(email="jan@example.com", password=PASSWORD)
    c = TestClient(app, base_url="https://testserver")
    r = c.post("/api/auth/login", json=_creds())
    header = r.headers["set-cookie"].lower()
    assert f"samesite={samesite}" in header and "secure" in header
    out = c.post("/api/auth/logout").headers["set-cookie"].lower()
    assert f"samesite={samesite}" in out and "secure" in out and "max-age=0" in out


def test_logout_all(make_user) -> None:
    a, _ = _logged_in(make_user)
    b = TestClient(app)
    b.post("/api/auth/login", json=_creds())
    other, _ = _logged_in(make_user, email="ola@example.com")
    r = a.post("/api/auth/logout-all")
    assert r.status_code == 204
    assert a.get("/api/auth/me").status_code == 401
    assert b.get("/api/auth/me").status_code == 401
    assert other.get("/api/auth/me").status_code == 200


# --- password change ---


def test_change_password_revokes_other_sessions(make_user, db: Session) -> None:
    a, user = _logged_in(make_user)
    b = TestClient(app)
    b.post("/api/auth/login", json=_creds())
    old_token = a.cookies[SESSION_COOKIE]
    r = a.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert r.status_code == 204
    assert a.cookies[SESSION_COOKIE] != old_token  # current device gets a fresh session
    assert a.get("/api/auth/me").status_code == 200
    assert b.get("/api/auth/me").status_code == 401
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 1
    db.expire_all()
    assert db.get(User, user.id).password_changed_at is not None
    fresh = TestClient(app)
    assert fresh.post("/api/auth/login", json=_creds()).status_code == 401
    assert fresh.post("/api/auth/login", json=_creds(password=NEW_PASSWORD)).status_code == 200


def test_change_password_wrong_current_403(make_user) -> None:
    a, _ = _logged_in(make_user)
    r = a.post(
        "/api/auth/password",
        json={"current_password": "zle-haslo-123", "new_password": NEW_PASSWORD},
    )
    assert r.status_code == 403
    assert r.json() == {"detail": "Nieprawidłowe hasło"}
    assert a.get("/api/auth/me").status_code == 200


@pytest.mark.parametrize("new", ["krotkie", PASSWORD, "jan@example.com"])
def test_change_password_policy(make_user, new: str) -> None:
    a, _ = _logged_in(make_user)
    r = a.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": new})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)


def test_change_password_rate_limited(make_user) -> None:
    a, _ = _logged_in(make_user)
    limit, _ = ratelimit.LOGIN_FAILS_PER_EMAIL
    body = {"current_password": "zle-haslo-123", "new_password": NEW_PASSWORD}
    for _ in range(limit):
        assert a.post("/api/auth/password", json=body).status_code == 403
    assert a.post("/api/auth/password", json=body).status_code == 429


# --- account deletion ---


def test_delete_account_cascades(make_user, db: Session, category_id) -> None:
    a, user = _logged_in(make_user)
    other, other_user = _logged_in(make_user, email="ola@example.com")
    uid_a, uid_b = user.id, other_user.id
    for uid in (uid_a, uid_b):
        db.add(
            Transaction(
                user_id=uid,
                date=dt.date(2026, 10, 1),
                amount=Decimal("-12.50"),
                base_amount=Decimal("-12.50"),
                description="Zakupy",
                category_id=category_id("Jedzenie"),
                source="manual",
            )
        )
        db.add(
            Holding(
                user_id=uid,
                name="ETF",
                asset_class="etf",
                quantity=Decimal("1"),
                purchase_price=Decimal("100.00"),
            )
        )
    db.commit()

    r = a.request("DELETE", "/api/auth/account", json={"password": PASSWORD})
    assert r.status_code == 204
    assert "max-age=0" in r.headers["set-cookie"].lower()
    db.expire_all()
    assert db.get(User, uid_a) is None
    for model in (Transaction, Holding, AuthSession):
        owners = set(db.scalars(select(model.user_id)).all())
        assert owners == {uid_b}, model.__name__
    assert a.get("/api/auth/me").status_code == 401
    assert TestClient(app).post("/api/auth/login", json=_creds()).status_code == 401
    assert other.get("/api/auth/me").status_code == 200
    # UC-08 open question: the address can be used again for a new account
    r = TestClient(app).post("/api/auth/register", json=_creds())
    assert r.status_code == 201


def test_delete_account_wrong_password(make_user, db: Session) -> None:
    a, user = _logged_in(make_user)
    r = a.request("DELETE", "/api/auth/account", json={"password": "zle-haslo-123"})
    assert r.status_code == 403
    assert db.get(User, user.id) is not None
    assert a.get("/api/auth/me").status_code == 200


def test_every_fk_to_users_cascades(db: Session) -> None:
    rows = db.execute(
        text(
            "SELECT c.conrelid::regclass::text, c.confdeltype FROM pg_constraint c "
            "WHERE c.contype = 'f' AND c.confrelid = 'users'::regclass"
        )
    ).all()
    assert rows
    assert {table for table, action in rows if action != "c"} == set()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/auth/logout-all"),
        ("post", "/api/auth/password"),
        ("delete", "/api/auth/account"),
    ],
)
def test_account_endpoints_require_login(client: TestClient, method: str, path: str) -> None:
    assert client.request(method.upper(), path, json={}).status_code in (401, 422)
    body = (
        {"password": PASSWORD}
        if path.endswith("account")
        else {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    )
    assert client.request(method.upper(), path, json=body).status_code == 401
