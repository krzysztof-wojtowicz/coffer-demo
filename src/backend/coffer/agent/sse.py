import json
import queue
import threading
from collections.abc import Callable, Iterator
from typing import Any

from pydantic import BaseModel

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

# Proxies in front of the API (the Vercel rewrite: 120 s to the first byte; Render) drop
# connections that stay silent too long, and an LLM call can take tens of seconds. An SSE
# comment line is sent at once and then every PING_INTERVAL_S while no event arrives;
# EventSource and our parser (features/assistant/sse.ts) ignore comment lines.
PING_INTERVAL_S = 15.0
PING = ": ping\n\n"

_DONE = object()


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def format_event(event: dict[str, Any]) -> str:
    etype = event["type"]
    payload = event.get("data") if "data" in event else {"message": event.get("message", "")}
    return f"event: {etype}\ndata: {json.dumps(_jsonable(payload), ensure_ascii=False)}\n\n"


def stream_events(
    work: Callable[[Callable[[dict[str, Any]], None]], None],
) -> Iterator[str]:
    """Run `work(on_event)` in a worker thread and yield its events as SSE frames.

    Yields a keep-alive comment immediately and whenever the worker is silent for
    PING_INTERVAL_S.
    """
    q: queue.Queue[Any] = queue.Queue()

    def runner() -> None:
        try:
            work(q.put)
        finally:
            q.put(_DONE)

    threading.Thread(target=runner, daemon=True).start()
    yield PING
    while True:
        try:
            item = q.get(timeout=PING_INTERVAL_S)
        except queue.Empty:
            yield PING
            continue
        if item is _DONE:
            return
        yield format_event(item)
