"""Accounts: registration, password storage, login/logout, access control, rate limits,
password change and account deletion. Sections follow openspec/specs/accounts."""

import datetime as dt
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from argon2.low_level import Type
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from coffer.accounts import ratelimit, service
from coffer.accounts.models import AuthSession, User
from coffer.accounts.policy import common_passwords, password_problems
from coffer.accounts.ratelimit import SlidingWindowLimiter
from coffer.accounts.tokens import SESSION_COOKIE, hash_token
from coffer.cash.models import OpeningBalance
from coffer.core.config import Settings, get_settings
from coffer.imports.models import ImportDraft
from coffer.main import app
from coffer.portfolio.models import Holding
from coffer.profile.models import InvestmentProfile
from coffer.transactions.models import Transaction

PASSWORD = "Kot-w-butach-42"
NEW_PASSWORD = "Pies-w-kaloszach-7"
WRONG = "zle-haslo-12345"
EMAIL = "jan@example.com"
VICTIM = "victim@example.com"
FRONT_LIST = Path(__file__).resolve().parents[3] / "frontend/src/features/auth/commonPasswords.json"


def _creds(email: str = EMAIL, password: str = PASSWORD) -> dict[str, str]:
    return {"display_name": "Jan", "email": email, "password": password}


def _lcreds(email: str = EMAIL, password: str = PASSWORD) -> dict[str, str]:
    return {"email": email, "password": password}


def _login(email: str = EMAIL, password: str = PASSWORD, **kw: object) -> TestClient:
    c = TestClient(app, **kw)  # pyright: ignore[reportArgumentType]
    r = c.post("/api/auth/login", json=_lcreds(email, password))
    assert r.status_code == 200, r.text
    return c


def _logged_in(make_user, email: str = EMAIL) -> tuple[TestClient, User]:
    user = make_user(email=email, password=PASSWORD)
    return _login(email), user


def _sessions(db: Session) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(AuthSession)) or 0


def _login_from(ip: str, email: str, password: str = WRONG) -> int:
    with TestClient(app, client=(ip, 50000)) as c:
        return c.post("/api/auth/login", json={"email": email, "password": password}).status_code


class _SlowHasher:
    def __init__(self) -> None:
        self.active = 0
        self.peak = 0
        self._lock = threading.Lock()

    def _work(self) -> None:
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        time.sleep(0.05)
        with self._lock:
            self.active -= 1

    def hash(self, password: str) -> str:
        self._work()
        return "h"

    def verify(self, hash: str, password: str) -> bool:
        self._work()
        return True


# --- Requirement: Registration (F01) ---


def test_register_creates_user_and_logs_in(client: TestClient, db: Session) -> None:
    r = client.post("/api/auth/register", json=_creds())
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"id", "email", "display_name"}
    assert body["display_name"] == "Jan"
    assert body["email"] == "jan@example.com"
    assert SESSION_COOKIE in client.cookies
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == body
    assert db.scalars(select(User)).one().id == body["id"]


def test_register_cookie_attributes(client: TestClient) -> None:
    r = client.post("/api/auth/register", json=_creds())
    header = r.headers["set-cookie"]
    lower = header.lower()
    assert header.startswith(f"{SESSION_COOKIE}=")
    assert "httponly" in lower
    assert "samesite=lax" in lower
    assert "path=/" in lower
    ttl = get_settings().session_ttl_days * 86400
    assert f"max-age={ttl}" in lower
    assert ("secure" in lower.replace("samesite", "")) == get_settings().cookie_secure


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


def test_register_invalid_creates_no_user(client: TestClient, db: Session) -> None:
    client.post("/api/auth/register", json=_creds(password="krotki"))
    assert db.scalars(select(User)).all() == []


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
    r = client.post("/api/auth/login", json=_lcreds(password=secret))
    assert r.status_code == 422
    assert secret not in r.text and "najwyżej 128" in r.json()["detail"]


def test_common_password_lists_in_sync() -> None:
    front = json.loads(FRONT_LIST.read_text(encoding="utf-8"))
    assert set(front) == set(common_passwords())


@pytest.mark.parametrize("variant", ["JAN@EXAMPLE.COM", "  Jan@Example.com\t", "jAn@eXaMpLe.CoM"])
def test_login_any_case(client: TestClient, variant: str) -> None:
    assert (
        client.post("/api/auth/register", json=_creds(email="Jan@Example.com ")).status_code == 201
    )
    assert TestClient(app).post("/api/auth/login", json=_lcreds(email=variant)).status_code == 200
    r = TestClient(app).post("/api/auth/register", json=_creds(email=variant))
    assert r.status_code == 409


def test_login_case_insensitive_for_legacy_mixed_case_row(client: TestClient, db: Session) -> None:
    db.add(
        User(
            email="Jan@Example.com",
            display_name="Jan",
            password_hash=PasswordHasher().hash(PASSWORD),
        )
    )
    db.commit()
    assert client.post("/api/auth/login", json=_lcreds(email="jan@example.com")).status_code == 200
    r = TestClient(app).post("/api/auth/register", json=_creds(email="JAN@example.com"))
    assert r.status_code == 409


def test_db_unique_index_on_email_is_case_insensitive(db: Session) -> None:
    db.add(User(email="jan@example.com", display_name="Jan", password_hash="x"))
    db.commit()
    db.add(User(email="JAN@example.com", display_name="Jan", password_hash="x"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# --- Requirement: Password storage (N01) ---


def test_hash_password_is_argon2_and_salted() -> None:
    h1 = service.hash_password("haslo12345")
    h2 = service.hash_password("haslo12345")
    assert h1.startswith("$argon2")
    assert "haslo12345" not in h1
    assert h1 != h2


def test_verify_password() -> None:
    h = service.hash_password("haslo12345")
    assert service.verify_password(h, "haslo12345") is True
    assert service.verify_password(h, "Haslo12345") is False
    assert service.verify_password(h, "") is False


def test_verify_password_garbage_hash_is_false() -> None:
    assert service.verify_password("to-nie-jest-hash", "haslo12345") is False


def test_hash_uses_explicit_argon2id_params() -> None:
    h = service.hash_password(PASSWORD)
    assert h.startswith("$argon2id$v=19$m=19456,t=2,p=1$")


def test_register_stores_only_token_hash(client: TestClient, db: Session) -> None:
    client.post("/api/auth/register", json=_creds())
    token = client.cookies[SESSION_COOKIE]
    row = db.scalars(select(AuthSession)).one()
    assert row.token_hash == hash_token(token)
    assert row.token_hash != token


def test_register_and_password_change_store_current_params(client: TestClient, db: Session) -> None:
    assert client.post("/api/auth/register", json=_creds()).status_code == 201
    r = client.post(
        "/api/auth/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    )
    assert r.status_code == 204
    db.expire_all()
    stored = db.scalars(select(User.password_hash)).one()
    assert stored.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert PASSWORD not in stored and NEW_PASSWORD not in stored


@pytest.mark.parametrize(
    "old_hasher",
    [
        PasswordHasher(),  # library defaults (m=64 MiB, t=3, p=4)
        PasswordHasher(time_cost=1, memory_cost=8 * 1024, parallelism=1),
        PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1, type=Type.I),
    ],
    ids=["defaults", "weaker", "argon2i"],
)
def test_login_upgrades_any_outdated_hash(make_user, db: Session, old_hasher) -> None:
    user = make_user(email=EMAIL, password="placeholder")
    user.password_hash = old_hasher.hash(PASSWORD)
    db.commit()
    old = user.password_hash
    _login()
    db.expire_all()
    new = db.get(User, user.id).password_hash
    assert new != old
    assert new.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    _login()  # new hash still verifies


def test_login_keeps_current_hash(make_user, db: Session) -> None:
    user = make_user(email=EMAIL, password="placeholder")
    user.password_hash = service.hash_password(PASSWORD)
    db.commit()
    current = user.password_hash
    _login()
    db.expire_all()
    assert db.get(User, user.id).password_hash == current  # no needless rewrite


def test_failed_login_does_not_rehash(client: TestClient, make_user, db: Session) -> None:
    user = make_user(email="jan@example.com", password=PASSWORD)
    client.post("/api/auth/login", json=_lcreds(password="zle-haslo-123"))
    db.expire_all()
    assert db.get(User, user.id).password_hash == user.password_hash


def test_hash_concurrency_capped_by_setting(monkeypatch) -> None:
    # contract: COFFER_PASSWORD_HASH_CONCURRENCY (default 2) bounds parallel hash/verify
    assert service.HASH_CONCURRENCY == get_settings().password_hash_concurrency
    assert Settings(_env_file=None).password_hash_concurrency == 2  # pyright: ignore[reportCallIssue]
    fake = _SlowHasher()
    monkeypatch.setattr(service, "_hasher", fake)
    jobs = [lambda: service.hash_password("x")] * 8 + [
        lambda: service.verify_password("h", "x")
    ] * 8
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda f: f(), jobs))
    assert fake.peak == service.HASH_CONCURRENCY


# --- Requirement: Login and logout ---


def test_login_success(client: TestClient, make_user) -> None:
    user = make_user(email="jan@example.com", password=PASSWORD)
    r = client.post("/api/auth/login", json=_lcreds())
    assert r.status_code == 200
    assert r.json()["id"] == user.id and r.json()["email"] == "jan@example.com"
    assert r.json()["display_name"]
    assert SESSION_COOKIE in client.cookies
    header = r.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header
    assert f"max-age={get_settings().session_ttl_days * 86400}" in header
    me = client.get("/api/auth/me").json()
    assert me["id"] == user.id and me["email"] == "jan@example.com" and me["display_name"]


def test_login_wrong_and_unknown_same_message(client: TestClient, make_user) -> None:
    make_user(email="jan@example.com", password=PASSWORD)
    wrong = client.post("/api/auth/login", json=_lcreds(password="zlehaslo12345"))
    unknown = client.post("/api/auth/login", json=_lcreds(email="nikt@example.com"))
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Nieprawidłowy e-mail lub hasło"}
    assert SESSION_COOKIE not in client.cookies


def test_unknown_email_verifies_dummy_hash(db: Session, monkeypatch) -> None:
    calls: list[str] = []
    real = service.verify_password

    def spy(h: str, p: str) -> bool:
        calls.append(h)
        return real(h, p)

    monkeypatch.setattr(service, "verify_password", spy)
    assert service.authenticate(db, "nikt@example.com", PASSWORD) is None
    assert calls == [service._DUMMY_HASH]


def test_login_rejects_129_chars_without_hashing_or_counting(make_user, monkeypatch) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    called: list[int] = []
    monkeypatch.setattr(service, "verify_password", lambda *a: called.append(1) or False)
    c = TestClient(app)
    for _ in range(ratelimit.LOGIN_FAILS_PER_EMAIL[0] + 2):
        assert c.post("/api/auth/login", json=_lcreds(password="x" * 129)).status_code == 422
    assert called == []
    monkeypatch.undo()
    assert c.post("/api/auth/login", json=_lcreds()).status_code == 200  # not locked out


def test_login_accepts_128_chars_input(make_user) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    r = TestClient(app).post("/api/auth/login", json=_lcreds(password="x" * 128))
    assert r.status_code == 401


@pytest.mark.parametrize("field", ["current_password", "new_password"])
def test_password_change_rejects_129_chars(make_user, field: str) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    c = _login()
    body = {"current_password": PASSWORD, "new_password": NEW_PASSWORD} | {field: "x" * 129}
    assert c.post("/api/auth/password", json=body).status_code == 422


def test_delete_account_rejects_129_chars(make_user) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    c = _login()
    r = c.request("DELETE", "/api/auth/account", json={"password": "x" * 129})
    assert r.status_code == 422


def test_login_creates_independent_sessions(client: TestClient, make_user, db: Session) -> None:
    make_user(email="jan@example.com", password=PASSWORD)
    other = TestClient(client.app)
    client.post("/api/auth/login", json=_lcreds())
    other.post("/api/auth/login", json=_lcreds())
    assert client.cookies[SESSION_COOKIE] != other.cookies[SESSION_COOKIE]
    assert len(db.scalars(select(AuthSession)).all()) == 2
    assert client.get("/api/auth/me").status_code == 200
    assert other.get("/api/auth/me").status_code == 200


def test_me_without_session_401(client: TestClient) -> None:
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json() == {"detail": "Wymagane logowanie"}


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
    header = r.headers["set-cookie"].lower()
    assert header.startswith(f"{SESSION_COOKIE}=")
    assert "max-age=0" in header or "expires=" in header
    assert SESSION_COOKIE not in client.cookies
    assert client.get("/api/auth/me").status_code == 401


def test_logout_without_session_204(client: TestClient) -> None:
    assert client.post("/api/auth/logout").status_code == 204


def test_logout_only_current_session(client: TestClient, make_user, db: Session) -> None:
    make_user(email="jan@example.com", password=PASSWORD)
    other = TestClient(client.app)
    client.post("/api/auth/login", json=_lcreds())
    other.post("/api/auth/login", json=_lcreds())
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    assert other.get("/api/auth/me").status_code == 200
    assert len(db.scalars(select(AuthSession)).all()) == 1


def test_failed_login_keeps_existing_session(make_user) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    c = _login()
    assert c.post("/api/auth/login", json=_lcreds(password=WRONG)).status_code == 401
    assert c.get("/api/auth/me").status_code == 200


def test_login_rotates_existing_session(make_user, db: Session) -> None:
    c, _ = _logged_in(make_user)
    first = c.cookies[SESSION_COOKIE]
    assert c.post("/api/auth/login", json=_lcreds()).status_code == 200
    assert c.cookies[SESSION_COOKIE] != first
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 1
    replay = TestClient(app)
    replay.cookies.set(SESSION_COOKIE, first)
    assert replay.get("/api/auth/me").status_code == 401


def test_login_rotation_does_not_touch_other_devices(make_user, db: Session) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    phone = _login()
    laptop = _login()
    old = laptop.cookies[SESSION_COOKIE]
    assert laptop.post("/api/auth/login", json=_lcreds()).status_code == 200
    assert laptop.cookies[SESSION_COOKIE] != old
    assert phone.get("/api/auth/me").status_code == 200
    assert _sessions(db) == 2


def test_register_purges_expired_sessions_and_creates_exactly_one(
    client: TestClient, make_user, db: Session
) -> None:
    make_user(email="old@example.com", password=PASSWORD)
    _login("old@example.com")
    db.query(AuthSession).update({"expires_at": dt.datetime.now(dt.UTC) - dt.timedelta(days=1)})
    db.commit()
    assert client.post("/api/auth/register", json=_creds()).status_code == 201
    db.expire_all()
    rows = db.scalars(select(AuthSession)).all()
    assert len(rows) == 1  # expired gone, no double session after registration
    assert rows[0].token_hash == hash_token(client.cookies[SESSION_COOKIE])
    assert client.get("/api/auth/me").json()["email"] == EMAIL


def test_logout_all(make_user) -> None:
    a, _ = _logged_in(make_user)
    b = TestClient(app)
    b.post("/api/auth/login", json=_lcreds())
    other, _ = _logged_in(make_user, email="ola@example.com")
    r = a.post("/api/auth/logout-all")
    assert r.status_code == 204
    assert a.get("/api/auth/me").status_code == 401
    assert b.get("/api/auth/me").status_code == 401
    assert other.get("/api/auth/me").status_code == 200


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/api/auth/me", None),
        ("POST", "/api/auth/logout-all", None),
        (
            "POST",
            "/api/auth/password",
            {"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        ),
        ("DELETE", "/api/auth/account", {"password": PASSWORD}),
    ],
)
@pytest.mark.parametrize("cookie", ["none", "garbage", "expired", "logged_out"])
def test_account_endpoints_401(make_user, db: Session, method, path, body, cookie: str) -> None:
    user = make_user(email=EMAIL, password=PASSWORD)
    c = TestClient(app)
    if cookie == "garbage":
        c.cookies.set(SESSION_COOKIE, "nie-ma-takiej-sesji")
    elif cookie == "expired":
        c = _login()
        db.query(AuthSession).filter(AuthSession.user_id == user.id).update(
            {"expires_at": dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)}
        )
        db.commit()
    elif cookie == "logged_out":
        c = _login()
        token = c.cookies[SESSION_COOKIE]
        c.post("/api/auth/logout")
        c.cookies.set(SESSION_COOKIE, token)  # replay (UC-09 4a)
    r = c.request(method, path, json=body)
    assert r.status_code == 401
    assert r.json() == {"detail": "Wymagane logowanie"}
    db.expire_all()
    assert db.get(User, user.id) is not None


@pytest.mark.parametrize(("samesite", "secure"), [("lax", False), ("strict", True)])
def test_cookie_attributes_on_every_set_and_clear(make_user, monkeypatch, samesite, secure) -> None:
    monkeypatch.setattr(get_settings(), "cookie_samesite", samesite)
    monkeypatch.setattr(get_settings(), "cookie_secure", secure)
    make_user(email=EMAIL, password=PASSWORD)

    def check(header: str, cleared: bool) -> None:
        h = header.lower()
        assert h.startswith(f"{SESSION_COOKIE}=")
        assert "httponly" in h and "path=/" in h
        assert f"samesite={samesite}" in h
        assert ("secure" in h) is secure
        assert ("max-age=0" in h) is cleared

    c = TestClient(app, base_url="https://testserver")
    check(c.post("/api/auth/login", json=_lcreds()).headers["set-cookie"], cleared=False)
    body = {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    check(c.post("/api/auth/password", json=body).headers["set-cookie"], cleared=False)
    check(c.post("/api/auth/logout-all").headers["set-cookie"], cleared=True)
    c = _login(password=NEW_PASSWORD, base_url="https://testserver")
    r = c.request("DELETE", "/api/auth/account", json={"password": NEW_PASSWORD})
    check(r.headers["set-cookie"], cleared=True)
    r = TestClient(app, base_url="https://testserver").post(
        "/api/auth/register", json=_creds("nowy@example.com")
    )
    check(r.headers["set-cookie"], cleared=False)


# --- Requirement: Rate limiting of credential endpoints ---


def test_login_rate_limit_per_email(client: TestClient, make_user) -> None:
    make_user(email="jan@example.com", password=PASSWORD)
    limit, window = ratelimit.LOGIN_FAILS_PER_EMAIL
    for _ in range(limit):
        r = client.post("/api/auth/login", json=_lcreds(password="zle-haslo-123"))
        assert r.status_code == 401
    r = client.post("/api/auth/login", json=_lcreds())  # even the right password
    assert r.status_code == 429
    assert "Zbyt wiele prób" in r.json()["detail"]
    assert 0 < int(r.headers["Retry-After"]) <= window
    # another account from the same IP is not locked yet
    make_user(email="ola@example.com", password=PASSWORD)
    assert client.post("/api/auth/login", json=_lcreds(email="ola@example.com")).status_code == 200


def test_login_rate_limit_per_ip(client: TestClient) -> None:
    limit, _ = ratelimit.LOGIN_FAILS_PER_IP
    for i in range(limit):
        r = client.post("/api/auth/login", json=_lcreds(email=f"u{i}@example.com"))
        assert r.status_code == 401
    r = client.post("/api/auth/login", json=_lcreds(email="new@example.com"))
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_successful_login_resets_email_counter(client: TestClient, make_user) -> None:
    make_user(email="jan@example.com", password=PASSWORD)
    limit, _ = ratelimit.LOGIN_FAILS_PER_EMAIL
    for _ in range(limit - 1):
        client.post("/api/auth/login", json=_lcreds(password="zle-haslo-123"))
    assert client.post("/api/auth/login", json=_lcreds()).status_code == 200
    for _ in range(limit - 1):
        client.post("/api/auth/login", json=_lcreds(password="zle-haslo-123"))
    assert client.post("/api/auth/login", json=_lcreds()).status_code == 200


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


def _assert_429(r) -> None:
    assert r.status_code == 429
    assert "Zbyt wiele prób" in r.json()["detail"]
    assert int(r.headers["Retry-After"]) > 0


def test_register_429_has_retry_after_and_polish_message() -> None:
    limit, window = ratelimit.REGISTER_PER_IP
    for i in range(limit):
        TestClient(app).post("/api/auth/register", json=_creds(email=f"u{i}@example.com"))
    r = TestClient(app).post("/api/auth/register", json=_creds(email="late@example.com"))
    _assert_429(r)
    assert int(r.headers["Retry-After"]) <= window


def test_rate_limit_key_is_case_insensitive(make_user) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    c = TestClient(app)
    for i in range(ratelimit.LOGIN_FAILS_PER_EMAIL[0]):
        variant = EMAIL.upper() if i % 2 else f"  {EMAIL}"
        assert (
            c.post("/api/auth/login", json=_lcreds(email=variant, password=WRONG)).status_code
            == 401
        )
    assert c.post("/api/auth/login", json=_lcreds()).status_code == 429


def test_wrong_password_on_delete_counts_towards_login_limit(make_user, db: Session) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    c = _login()
    limit, _ = ratelimit.LOGIN_FAILS_PER_EMAIL
    for _ in range(limit):
        assert c.request("DELETE", "/api/auth/account", json={"password": WRONG}).status_code == 403
    _assert_429(c.request("DELETE", "/api/auth/account", json={"password": PASSWORD}))
    _assert_429(TestClient(app).post("/api/auth/login", json=_lcreds()))
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_mixed_failures_share_one_counter(make_user) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    c = _login()
    limit, _ = ratelimit.LOGIN_FAILS_PER_EMAIL
    half = limit // 2
    for _ in range(half):
        TestClient(app).post("/api/auth/login", json=_lcreds(password=WRONG))
    for _ in range(limit - half):
        body = {"current_password": WRONG, "new_password": NEW_PASSWORD}
        assert c.post("/api/auth/password", json=body).status_code == 403
    _assert_429(TestClient(app).post("/api/auth/login", json=_lcreds()))


def test_parallel_failed_logins_cannot_exceed_limit(make_user, monkeypatch) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    limit, _ = ratelimit.LOGIN_FAILS_PER_EMAIL
    n = limit + 5
    barrier = threading.Barrier(n)

    def slow_wrong(*_: object) -> bool:
        try:  # every request that got past the limit check waits here for the others
            barrier.wait(timeout=3)
        except threading.BrokenBarrierError:
            pass
        return False

    monkeypatch.setattr(service, "verify_password", slow_wrong)

    def attempt(i: int) -> int:
        body = _creds(password=f"zle-haslo-{i:05d}")
        return TestClient(app).post("/api/auth/login", json=body).status_code

    with ThreadPoolExecutor(n) as ex:
        codes = list(ex.map(attempt, range(n)))
    assert codes.count(401) <= limit, codes


def _set_hops(monkeypatch, hops: int) -> None:
    monkeypatch.setattr(get_settings(), "trusted_proxy_hops", hops)


def test_spoofed_forwarded_for_ignored_without_trusted_hops(monkeypatch) -> None:
    _set_hops(monkeypatch, 0)
    limit, _ = ratelimit.LOGIN_FAILS_PER_IP
    c = TestClient(app)
    for i in range(limit):
        h = {"X-Forwarded-For": f"10.9.{i}.1"}
        assert (
            c.post("/api/auth/login", json=_lcreds(f"u{i}@example.com"), headers=h).status_code
            == 401
        )
    r = c.post(
        "/api/auth/login", json=_lcreds("x@example.com"), headers={"X-Forwarded-For": "1.1.1.1"}
    )
    _assert_429(r)


def test_one_trusted_hop_uses_last_forwarded_entry(monkeypatch) -> None:
    _set_hops(monkeypatch, 1)
    limit, _ = ratelimit.LOGIN_FAILS_PER_IP
    c = TestClient(app)
    for i in range(limit):
        # the client-controlled left part changes, the proxy-appended right part does not
        h = {"X-Forwarded-For": f"6.6.6.{i}, 1.2.3.4"}
        c.post("/api/auth/login", json=_lcreds(f"u{i}@example.com"), headers=h)
    blocked = c.post(
        "/api/auth/login", json=_lcreds("x@example.com"), headers={"X-Forwarded-For": "1.2.3.4"}
    )
    _assert_429(blocked)
    other = c.post(
        "/api/auth/login", json=_lcreds("x@example.com"), headers={"X-Forwarded-For": "1.2.3.5"}
    )
    assert other.status_code == 401


def test_two_trusted_hops_ignore_spoofed_prefix(monkeypatch) -> None:
    _set_hops(monkeypatch, 2)
    limit, _ = ratelimit.REGISTER_PER_IP
    for i in range(limit):
        h = {"X-Forwarded-For": f"6.6.{i}.6, 1.2.3.4, 76.76.21.1"}
        TestClient(app).post("/api/auth/register", json=_creds(f"u{i}@example.com"), headers=h)
    h = {"X-Forwarded-For": "9.9.9.9, 1.2.3.4, 76.76.21.9"}
    _assert_429(TestClient(app).post("/api/auth/register", json=_creds("z@example.com"), headers=h))


def test_key_flood_does_not_reset_email_lockout(make_user, monkeypatch) -> None:
    monkeypatch.setattr(ratelimit, "_MAX_KEYS", 30)
    make_user(email=VICTIM)
    limit = ratelimit.LOGIN_FAILS_PER_EMAIL[0]
    for _ in range(limit):
        assert _login_from("10.0.0.1", VICTIM) == 401
    assert _login_from("10.0.0.1", VICTIM) == 429

    # Flood: one attempt per random e-mail, a fresh IP every few attempts (2 keys each).
    for i in range(40):
        _login_from(f"10.1.{i // 5}.{i % 5}", f"flood{i}@example.com")

    # Victim's correct password from a fresh IP: still locked, guessing must not resume.
    assert _login_from("10.9.9.9", VICTIM, "haslo12345") == 429


# --- Requirement: Password change ---


def test_change_password_revokes_other_sessions(make_user, db: Session) -> None:
    a, user = _logged_in(make_user)
    b = TestClient(app)
    b.post("/api/auth/login", json=_lcreds())
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
    assert fresh.post("/api/auth/login", json=_lcreds()).status_code == 401
    assert fresh.post("/api/auth/login", json=_lcreds(password=NEW_PASSWORD)).status_code == 200


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


def test_wrong_current_password_with_weak_new_is_403_not_422(make_user) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    c = _login()
    r = c.post("/api/auth/password", json={"current_password": WRONG, "new_password": "abc"})
    assert r.status_code == 403


# --- Requirement: Account deletion (N09) ---


def _seed_everything(db: Session, uid: int, category_id: int) -> None:
    db.add(
        Transaction(
            user_id=uid,
            date=dt.date(2026, 10, 1),
            amount=Decimal("-12.50"),
            description="Zakupy",
            category_id=category_id,
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
    db.add(InvestmentProfile(user_id=uid, horizon="long", risk="low", preferred_classes=["etf"]))
    db.add(OpeningBalance(user_id=uid, amount=Decimal("1000.00"), as_of=dt.date(2026, 1, 1)))
    db.add(
        ImportDraft(
            id=f"draft-{uid}",
            user_id=uid,
            bank="mbank",
            filename="a.csv",
            rows=[],
            expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
        )
    )
    db.commit()


def test_delete_account_removes_data_of_every_module(make_user, db: Session, category_id) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    make_user(email="ola@example.com", password=PASSWORD)
    a, b = _login(), _login("ola@example.com")
    uid_a = a.get("/api/auth/me").json()["id"]
    uid_b = b.get("/api/auth/me").json()["id"]
    for uid in (uid_a, uid_b):
        _seed_everything(db, uid, category_id("Jedzenie"))
    assert a.request("DELETE", "/api/auth/account", json={"password": PASSWORD}).status_code == 204
    db.expire_all()
    models = (
        Transaction,
        Holding,
        InvestmentProfile,
        OpeningBalance,
        ImportDraft,
        AuthSession,
    )
    for model in models:
        owners = set(db.scalars(select(model.user_id)).all())
        assert owners == {uid_b}, model.__name__
    assert b.get("/api/auth/me").status_code == 200
    assert TestClient(app).post("/api/auth/login", json=_lcreds()).status_code == 401

    # same address can register again and starts with an empty account
    fresh = TestClient(app)
    r = fresh.post("/api/auth/register", json=_creds(password=NEW_PASSWORD))
    assert r.status_code == 201
    new_id = r.json()["id"]
    assert new_id != uid_a
    for model in models[:-1]:
        assert (
            db.scalar(select(func.count()).select_from(model).where(model.user_id == new_id)) == 0
        )


def test_delete_account_wrong_password(make_user, db: Session) -> None:
    a, user = _logged_in(make_user)
    r = a.request("DELETE", "/api/auth/account", json={"password": "zle-haslo-123"})
    assert r.status_code == 403
    assert db.get(User, user.id) is not None
    assert a.get("/api/auth/me").status_code == 200


# --- Display name ---

NAME_MSG = "Imię musi mieć od 1 do 50 znaków"


def test_register_stores_trimmed_display_name(client: TestClient, db: Session) -> None:
    r = client.post("/api/auth/register", json={**_creds(), "display_name": "  Ola  "})
    assert r.status_code == 201
    assert r.json()["display_name"] == "Ola"
    assert client.get("/api/auth/me").json()["display_name"] == "Ola"


def test_register_name_50_chars_ok(client: TestClient) -> None:
    r = client.post("/api/auth/register", json={**_creds(), "display_name": "a" * 50})
    assert r.status_code == 201


@pytest.mark.parametrize("name", [None, "", "   ", "a" * 51, "Jan\x00"])
def test_register_bad_display_name_422(client: TestClient, db: Session, name) -> None:
    body = _creds()
    if name is None:
        del body["display_name"]
    else:
        body["display_name"] = name
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 422
    if name is not None and "\x00" not in name:
        assert NAME_MSG in r.text
    assert db.scalars(select(User)).all() == []


def test_login_does_not_need_display_name(make_user) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    r = TestClient(app).post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["display_name"]


def test_patch_me_changes_name(make_user) -> None:
    c, _ = _logged_in(make_user)
    r = c.patch("/api/auth/me", json={"display_name": " Nowe "})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Nowe"
    assert c.get("/api/auth/me").json()["display_name"] == "Nowe"


@pytest.mark.parametrize("name", ["", "   ", "a" * 51])
def test_patch_me_invalid_keeps_old_name(make_user, name) -> None:
    c, _ = _logged_in(make_user)
    before = c.get("/api/auth/me").json()["display_name"]
    r = c.patch("/api/auth/me", json={"display_name": name})
    assert r.status_code == 422
    assert NAME_MSG in r.text
    assert c.get("/api/auth/me").json()["display_name"] == before


def test_patch_me_missing_field_422(make_user) -> None:
    c, _ = _logged_in(make_user)
    assert c.patch("/api/auth/me", json={}).status_code == 422


def test_patch_me_without_session_401(client: TestClient) -> None:
    assert client.patch("/api/auth/me", json={"display_name": "X"}).status_code == 401


def test_patch_me_affects_only_own_user(make_user) -> None:
    a, _ = _logged_in(make_user)
    make_user(email="ola@example.com", password=PASSWORD)
    b = _login("ola@example.com")
    before = b.get("/api/auth/me").json()["display_name"]
    a.patch("/api/auth/me", json={"display_name": "Zmienione"})
    assert b.get("/api/auth/me").json()["display_name"] == before


@pytest.mark.parametrize("name", ["Jan\nKowalski", "Jan‮Kowalski"])
def test_display_name_control_or_bidi_chars_422(make_user, client: TestClient, name) -> None:
    body = {**_creds(), "display_name": name}
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 422
    assert NAME_MSG in r.text
    c, _ = _logged_in(make_user, email="ola@example.com")
    before = c.get("/api/auth/me").json()["display_name"]
    r = c.patch("/api/auth/me", json={"display_name": name})
    assert r.status_code == 422
    assert NAME_MSG in r.text
    assert c.get("/api/auth/me").json()["display_name"] == before
