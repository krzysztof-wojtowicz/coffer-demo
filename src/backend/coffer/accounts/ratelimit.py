"""In-process sliding-window rate limiter for the auth endpoints.

Process memory (not a DB table) on purpose: production runs a single Render instance with
one uvicorn worker, so one process sees every request; it costs no DB writes per attempt and
needs no cleanup job. Trade-offs: counters reset on restart/redeploy, and running several
workers or instances would split them (then move this to a `login_attempts` table).
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request

from coffer.core.config import get_settings

# Failed logins (also wrong password on password change / account deletion). A successful
# login clears the per-e-mail counter only; failures already counted per IP stay counted.
LOGIN_FAILS_PER_EMAIL = (10, 15 * 60)
LOGIN_FAILS_PER_IP = (30, 15 * 60)
# Every registration attempt that passes schema validation, including ones rejected for a
# weak password or an already registered e-mail.
REGISTER_PER_IP = (10, 60 * 60)

_MAX_KEYS = 50_000


class SlidingWindowLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str, limit: int, window: float) -> int | None:
        """Seconds until the next attempt is allowed, or None if under the limit."""
        now = self._clock()
        with self._lock:
            hits = self._prune(key, now - window)
            if hits is None or len(hits) < limit:
                return None
            return max(1, math.ceil(hits[0] + window - now))

    def acquire(self, rules: list[tuple[str, int, float]]) -> int | None:
        """Atomically check every (key, limit, window) and, if none is exhausted, record one
        hit on each. Returns None on success, else the seconds to wait (nothing recorded).
        Checking and recording under one lock means N parallel requests cannot all slip
        past the check before any of them is counted."""
        now = self._clock()
        with self._lock:
            waits = []
            for key, limit, window in rules:
                hits = self._prune(key, now - window)
                if hits is not None and len(hits) >= limit:
                    waits.append(max(1, math.ceil(hits[0] + window - now)))
            if waits:
                return max(waits)
            if len(self._hits) >= _MAX_KEYS:
                self._hits.clear()  # memory bound under a flood of distinct keys
            for key, _, _ in rules:
                self._hits.setdefault(key, deque()).append(now)
            return None

    def release(self, key: str) -> None:
        """Undo the most recent hit on key (an attempt reserved by acquire that succeeded)."""
        with self._lock:
            hits = self._hits.get(key)
            if hits:
                hits.pop()
                if not hits:
                    del self._hits[key]

    def hit(self, key: str) -> None:
        now = self._clock()
        with self._lock:
            if len(self._hits) >= _MAX_KEYS:
                self._hits.clear()  # memory bound under a flood of distinct keys
            self._hits.setdefault(key, deque()).append(now)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)

    def _prune(self, key: str, cutoff: float) -> deque[float] | None:
        hits = self._hits.get(key)
        if hits is None:
            return None
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if not hits:
            del self._hits[key]
            return None
        return hits


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    """Client IP for rate limiting.

    With COFFER_TRUSTED_PROXY_HOPS=N > 0 the N-th address counted from the RIGHT of
    X-Forwarded-For is used (each trusted proxy appends the address it saw), never the
    leftmost one. Entries further left are client-controlled and never trusted. If the header
    has fewer than N entries, the leftmost (= the only proxy-written) entry is used.
    Limitation: with N=2 (Vercel -> Render) a client calling onrender.com directly, bypassing
    Vercel, controls entry N from the right too; only a direct-origin block would fix that.

    N=0 uses request.client.host. Locally that is the socket peer, but in the production image
    uvicorn runs with --proxy-headers --forwarded-allow-ips='*', which replaces it with the
    LEFTMOST X-Forwarded-For entry: a client calling onrender.com directly can spoof it, so the
    per-IP limit is best effort there. The per-e-mail limit applies regardless of the IP.
    """
    hops = get_settings().trusted_proxy_hops
    forwarded = request.headers.get("x-forwarded-for")
    if hops > 0 and forwarded:
        hosts = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hosts:
            return hosts[max(0, len(hosts) - hops)]
    return request.client.host if request.client else "unknown"


def too_many(seconds: int) -> HTTPException:
    minutes = max(1, math.ceil(seconds / 60))
    return HTTPException(
        status_code=429,
        detail=f"Zbyt wiele prób. Spróbuj ponownie za {minutes} min.",
        headers={"Retry-After": str(seconds)},
    )


def reserve(*checks: tuple[str, tuple[int, int]]) -> None:
    """Count one attempt on every (key, (limit, window)) atomically, or raise 429.

    Callers reserve BEFORE verifying a password and call limiter.release() for the keys that
    should not count when the attempt turns out fine (see accounts/api.py).
    """
    wait = limiter.acquire([(key, limit, window) for key, (limit, window) in checks])
    if wait is not None:
        raise too_many(wait)
