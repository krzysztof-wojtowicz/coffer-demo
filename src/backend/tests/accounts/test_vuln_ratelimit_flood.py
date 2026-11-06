"""Exploit: flooding the limiter with distinct keys must not wipe an existing lockout.

Attack: lock is reached on the victim's e-mail (brute force), then the attacker sends
attempts for many random e-mails from other IPs until the limiter hits its key cap. The cap
used to clear() every counter, so the victim's lockout vanished and guessing resumed.
_MAX_KEYS is shrunk so the flood fits in a test; production needs ~50k keys (many IPs or a
spoofed X-Forwarded-For, see ratelimit.client_ip).
"""

from fastapi.testclient import TestClient

from coffer.accounts import ratelimit
from coffer.main import app

VICTIM = "victim@example.com"


def _login(ip: str, email: str, password: str = "zle-haslo-123") -> int:
    with TestClient(app, client=(ip, 50000)) as c:
        return c.post("/api/auth/login", json={"email": email, "password": password}).status_code


def test_key_flood_does_not_reset_email_lockout(make_user, monkeypatch) -> None:
    monkeypatch.setattr(ratelimit, "_MAX_KEYS", 30)
    make_user(email=VICTIM)
    limit = ratelimit.LOGIN_FAILS_PER_EMAIL[0]
    for _ in range(limit):
        assert _login("10.0.0.1", VICTIM) == 401
    assert _login("10.0.0.1", VICTIM) == 429

    # Flood: one attempt per random e-mail, a fresh IP every few attempts (2 keys each).
    for i in range(40):
        _login(f"10.1.{i // 5}.{i % 5}", f"flood{i}@example.com")

    # Victim's correct password from a fresh IP: still locked, guessing must not resume.
    assert _login("10.9.9.9", VICTIM, "haslo12345") == 429
