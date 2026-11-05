import json
import queue
import threading
from collections.abc import Callable, Iterator
from typing import Any

from pydantic import BaseModel

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

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
    """Run `work(on_event)` in a worker thread and yield its events as SSE frames."""
    q: queue.Queue[Any] = queue.Queue()

    def runner() -> None:
        try:
            work(q.put)
        finally:
            q.put(_DONE)

    threading.Thread(target=runner, daemon=True).start()
    while True:
        item = q.get()
        if item is _DONE:
            return
        yield format_event(item)
