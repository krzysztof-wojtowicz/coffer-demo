"""Abuse guard for agent actions (separate from the AI daily limit, which counts model runs).

Every action call costs outbound requests (market data) and CPU even when no model runs
(`no_data`, no LLM), so each user gets a sliding-window call budget and at most a few runs in
parallel. In-process memory on purpose (single uvicorn worker on Render, like the auth limiter);
counters reset on restart.
"""

import threading
import time
from collections import deque
from collections.abc import Callable

# (calls, window in seconds); both must have room for a call to start.
WINDOWS: tuple[tuple[int, float], ...] = ((20, 60.0), (200, 24 * 3600.0))
MAX_PARALLEL = 2
RATE_MESSAGE = "Zbyt wiele uruchomień akcji. Spróbuj ponownie za chwilę."
PARALLEL_MESSAGE = "Poprzednie uruchomienie akcji jeszcze trwa. Poczekaj na jego wynik."


class ActionRateLimited(Exception):
    """The user exceeded the call budget or the parallel-run cap (HTTP 429)."""

    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ActionGuard:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._hits: dict[int, deque[float]] = {}
        self._running: dict[int, int] = {}

    def acquire(self, user_id: int) -> None:
        """Reserve one call for the user or raise ActionRateLimited; pair with release()."""
        now = self._clock()
        longest = max(window for _, window in WINDOWS)
        with self._lock:
            if self._running.get(user_id, 0) >= MAX_PARALLEL:
                raise ActionRateLimited(PARALLEL_MESSAGE, 5)
            hits = self._hits.setdefault(user_id, deque())
            while hits and hits[0] <= now - longest:
                hits.popleft()
            for limit, window in WINDOWS:
                recent = [h for h in hits if h > now - window]
                if len(recent) >= limit:
                    wait = max(1, int(recent[0] + window - now) + 1)
                    raise ActionRateLimited(RATE_MESSAGE, wait)
            hits.append(now)
            self._running[user_id] = self._running.get(user_id, 0) + 1

    def release(self, user_id: int) -> None:
        with self._lock:
            left = self._running.get(user_id, 0) - 1
            if left > 0:
                self._running[user_id] = left
            else:
                self._running.pop(user_id, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._running.clear()


guard = ActionGuard()
