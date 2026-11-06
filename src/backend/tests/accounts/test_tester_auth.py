"""Tester: accounts contract (hashing, rate limits, sessions, cookies, account deletion).

Written from the task contract and UC-01/08/09, not from the implementation.
"""

import datetime as dt
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from argon2 import PasswordHasher
from argon2.low_level import Type
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from coffer.accounts import ratelimit, service
from coffer.accounts.models import AuthSession, User
from coffer.accounts.tokens import SESSION_COOKIE, hash_token
from coffer.agent.models import AgentRun, Suggestion
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


def _creds(email: str = EMAIL, password: str = PASSWORD) -> dict[str, str]:
    return {"email": email, "password": password}


def _login(email: str = EMAIL, password: str = PASSWORD, **kw: object) -> TestClient:
    c = TestClient(app, **kw)  # pyright: ignore[reportArgumentType]
    r = c.post("/api/auth/login", json=_creds(email, password))
    assert r.status_code == 200, r.text
    return c


def _sessions(db: Session) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(AuthSession)) or 0


# --- hashing ---


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


# --- password length limit on every endpoint ---


def test_login_rejects_129_chars_without_hashing_or_counting(make_user, monkeypatch) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    called: list[int] = []
    monkeypatch.setattr(service, "verify_password", lambda *a: called.append(1) or False)
    c = TestClient(app)
    for _ in range(ratelimit.LOGIN_FAILS_PER_EMAIL[0] + 2):
        assert c.post("/api/auth/login", json=_creds(password="x" * 129)).status_code == 422
    assert called == []
    monkeypatch.undo()
    assert c.post("/api/auth/login", json=_creds()).status_code == 200  # not locked out


def test_login_accepts_128_chars_input(make_user) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    r = TestClient(app).post("/api/auth/login", json=_creds(password="x" * 128))
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


# --- e-mail normalization ---


@pytest.mark.parametrize("variant", ["JAN@EXAMPLE.COM", "  Jan@Example.com\t", "jAn@eXaMpLe.CoM"])
def test_login_any_case(client: TestClient, variant: str) -> None:
    assert (
        client.post("/api/auth/register", json=_creds(email="Jan@Example.com ")).status_code == 201
    )
    assert TestClient(app).post("/api/auth/login", json=_creds(email=variant)).status_code == 200
    r = TestClient(app).post("/api/auth/register", json=_creds(email=variant))
    assert r.status_code == 409


def test_rate_limit_key_is_case_insensitive(make_user) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    c = TestClient(app)
    for i in range(ratelimit.LOGIN_FAILS_PER_EMAIL[0]):
        variant = EMAIL.upper() if i % 2 else f"  {EMAIL}"
        assert (
            c.post("/api/auth/login", json=_creds(email=variant, password=WRONG)).status_code == 401
        )
    assert c.post("/api/auth/login", json=_creds()).status_code == 429


# --- rate limiting ---


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


def test_wrong_password_on_delete_counts_towards_login_limit(make_user, db: Session) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    c = _login()
    limit, _ = ratelimit.LOGIN_FAILS_PER_EMAIL
    for _ in range(limit):
        assert c.request("DELETE", "/api/auth/account", json={"password": WRONG}).status_code == 403
    _assert_429(c.request("DELETE", "/api/auth/account", json={"password": PASSWORD}))
    _assert_429(TestClient(app).post("/api/auth/login", json=_creds()))
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_mixed_failures_share_one_counter(make_user) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    c = _login()
    limit, _ = ratelimit.LOGIN_FAILS_PER_EMAIL
    half = limit // 2
    for _ in range(half):
        TestClient(app).post("/api/auth/login", json=_creds(password=WRONG))
    for _ in range(limit - half):
        body = {"current_password": WRONG, "new_password": NEW_PASSWORD}
        assert c.post("/api/auth/password", json=body).status_code == 403
    _assert_429(TestClient(app).post("/api/auth/login", json=_creds()))


def test_wrong_current_password_with_weak_new_is_403_not_422(make_user) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    c = _login()
    r = c.post("/api/auth/password", json={"current_password": WRONG, "new_password": "abc"})
    assert r.status_code == 403


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
            c.post("/api/auth/login", json=_creds(f"u{i}@example.com"), headers=h).status_code
            == 401
        )
    r = c.post(
        "/api/auth/login", json=_creds("x@example.com"), headers={"X-Forwarded-For": "1.1.1.1"}
    )
    _assert_429(r)


def test_one_trusted_hop_uses_last_forwarded_entry(monkeypatch) -> None:
    _set_hops(monkeypatch, 1)
    limit, _ = ratelimit.LOGIN_FAILS_PER_IP
    c = TestClient(app)
    for i in range(limit):
        # the client-controlled left part changes, the proxy-appended right part does not
        h = {"X-Forwarded-For": f"6.6.6.{i}, 1.2.3.4"}
        c.post("/api/auth/login", json=_creds(f"u{i}@example.com"), headers=h)
    blocked = c.post(
        "/api/auth/login", json=_creds("x@example.com"), headers={"X-Forwarded-For": "1.2.3.4"}
    )
    _assert_429(blocked)
    other = c.post(
        "/api/auth/login", json=_creds("x@example.com"), headers={"X-Forwarded-For": "1.2.3.5"}
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


# --- sessions and 401 ---


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


def test_login_rotation_does_not_touch_other_devices(make_user, db: Session) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    phone = _login()
    laptop = _login()
    old = laptop.cookies[SESSION_COOKIE]
    assert laptop.post("/api/auth/login", json=_creds()).status_code == 200
    assert laptop.cookies[SESSION_COOKIE] != old
    assert phone.get("/api/auth/me").status_code == 200
    assert _sessions(db) == 2


def test_failed_login_keeps_existing_session(make_user) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    c = _login()
    assert c.post("/api/auth/login", json=_creds(password=WRONG)).status_code == 401
    assert c.get("/api/auth/me").status_code == 200


def test_logout_all_then_login_again(make_user, db: Session) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    a, b = _login(), _login()
    assert a.post("/api/auth/logout-all").status_code == 204
    assert _sessions(db) == 0
    assert b.get("/api/auth/me").status_code == 401
    assert _login().get("/api/auth/me").status_code == 200


def test_password_change_old_token_replay_rejected(make_user) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    a = _login()
    old = a.cookies[SESSION_COOKIE]
    body = {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    assert a.post("/api/auth/password", json=body).status_code == 204
    replay = TestClient(app)
    replay.cookies.set(SESSION_COOKIE, old)
    assert replay.get("/api/auth/me").status_code == 401


def test_password_change_rejects_local_part_and_polish_message(make_user) -> None:
    make_user(email="jan.kowalski@example.com", password=PASSWORD)
    a = _login("jan.kowalski@example.com")
    body = {"current_password": PASSWORD, "new_password": "Jan.Kowalski"}
    r = a.post("/api/auth/password", json=body)
    assert r.status_code == 422
    assert "adres e-mail" in r.json()["detail"]


# --- cookie attributes ---


@pytest.mark.parametrize(("samesite", "secure"), [("lax", False), ("strict", True), ("none", True)])
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
    check(c.post("/api/auth/login", json=_creds()).headers["set-cookie"], cleared=False)
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


# --- account deletion (UC-08) ---


def _seed_everything(db: Session, uid: int, category_id: int) -> None:
    db.add(
        Transaction(
            user_id=uid,
            date=dt.date(2026, 10, 1),
            amount=Decimal("-12.50"),
            base_amount=Decimal("-12.50"),
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
    run = AgentRun(user_id=uid, task="surplus", prompt_version="v1", status="ok")
    db.add(run)
    db.flush()
    db.add(
        Suggestion(
            user_id=uid,
            agent_run_id=run.id,
            type="surplus",
            summary="s",
            rationale=[],
            disclaimer="d",
            model="m",
            data_snapshot={},
        )
    )
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
        AgentRun,
        Suggestion,
        ImportDraft,
        AuthSession,
    )
    for model in models:
        owners = set(db.scalars(select(model.user_id)).all())
        assert owners == {uid_b}, model.__name__
    assert b.get("/api/auth/me").status_code == 200

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


def test_delete_account_needs_password_field(make_user, db: Session) -> None:
    make_user(email=EMAIL, password=PASSWORD)
    c = _login()
    assert c.request("DELETE", "/api/auth/account").status_code == 422
    assert c.request("DELETE", "/api/auth/account", json={}).status_code == 422
    assert c.request("DELETE", "/api/auth/account", json={"password": ""}).status_code == 422
    assert db.scalar(select(func.count()).select_from(User)) == 1
