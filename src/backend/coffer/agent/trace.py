"""Run trace (E5-00 K4): the timeline of tool, model, validation and fallback steps."""

import json
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from coffer.agent.llm import LLMResponse
from coffer.agent.pricing import estimate_cost
from coffer.agent.tools.registry import ToolCall

MAX_OUTPUT_CHARS = 20_000

StepListener = Callable[[dict[str, Any]], None]


def _clip(output: dict[str, Any]) -> dict[str, Any] | str:
    text = json.dumps(output, ensure_ascii=False)
    return output if len(text) <= MAX_OUTPUT_CHARS else text[:MAX_OUTPUT_CHARS]


class RunTrace:
    """Collects everything persisted in `agent_runs` for one action run."""

    def __init__(self, on_step: StepListener | None = None) -> None:
        self._t0 = time.perf_counter()
        self._on_step = on_step
        self.steps: list[dict[str, Any]] = []
        self.messages: list[dict[str, str]] = []
        self.raw_outputs: list[str] = []
        self.validation_errors: list[str] = []
        self.llm_calls = 0
        self.model: str | None = None
        self.provider: str | None = None
        self.input_tokens: int | None = None
        self.output_tokens: int | None = None
        self.cost_usd: Decimal | None = None

    def now_ms(self) -> int:
        return int((time.perf_counter() - self._t0) * 1000)

    def _add(
        self, kind: str, name: str, started_ms: int, status: str, detail: dict[str, Any]
    ) -> dict[str, Any]:
        step = {
            "index": len(self.steps),
            "kind": kind,
            "name": name,
            "started_ms": started_ms,
            "duration_ms": max(self.now_ms() - started_ms, 0),
            "status": status,
            **detail,
        }
        self.steps.append(step)
        if self._on_step is not None:
            self._on_step({k: step[k] for k in ("index", "kind", "name", "status", "duration_ms")})
        return step

    def tool(self, call: ToolCall, started_ms: int, origin: str) -> None:
        self._add(
            "tool",
            call.name,
            started_ms,
            call.status,
            {
                "arguments": call.arguments,
                "output": _clip(call.output),
                "error": call.error,
                "origin": origin,
            },
        )

    def tool_error(
        self, name: str, arguments: dict[str, Any], message: str, started_ms: int, origin: str
    ) -> None:
        """A call that never ran: unknown or not allowed tool, bad arguments."""
        self._add(
            "tool",
            name or "?",
            started_ms,
            "error",
            {
                "arguments": arguments,
                "output": {"error": message},
                "error": message,
                "origin": origin,
            },
        )

    def llm(self, response: LLMResponse, started_ms: int, attempt: int) -> None:
        cost = estimate_cost(
            response.provider, response.model, response.input_tokens, response.output_tokens
        )
        self.llm_calls += 1
        self.model, self.provider = response.model, response.provider
        if response.input_tokens is not None:
            self.input_tokens = (self.input_tokens or 0) + response.input_tokens
        if response.output_tokens is not None:
            self.output_tokens = (self.output_tokens or 0) + response.output_tokens
        if cost is not None:
            self.cost_usd = (self.cost_usd or Decimal(0)) + cost
        self.raw_outputs.append(response.content)
        self._add(
            "llm",
            response.model,
            started_ms,
            "ok",
            {
                "provider": response.provider,
                "model": response.model,
                "attempt": attempt,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": None if cost is None else str(cost),
                "output": response.content,
                "error": None,
            },
        )

    def llm_error(self, message: str, started_ms: int, attempt: int) -> None:
        self.llm_calls += 1
        self._add(
            "llm",
            self.model or "llm",
            started_ms,
            "error",
            {"provider": self.provider, "model": self.model, "attempt": attempt, "error": message},
        )

    def validation(self, errors: list[str], started_ms: int) -> None:
        self.validation_errors.extend(errors)
        self._add(
            "validation", "validation", started_ms, "error" if errors else "ok", {"errors": errors}
        )

    def fallback(self, reason: str, started_ms: int) -> None:
        self._add("fallback", "fallback", started_ms, "ok", {"reason": reason})

    def limit(self, started_ms: int) -> None:
        self._add(
            "limit", "daily_limit", started_ms, "error", {"error": "Dzienny limit wyczerpany"}
        )

    def error(self, message: str, started_ms: int) -> None:
        self._add("error", "error", started_ms, "error", {"error": message})

    @property
    def tool_calls(self) -> list[dict[str, Any]]:
        """Legacy `agent_runs.tool_calls` view of the tool steps."""
        return [
            {
                "name": s["name"],
                "arguments": s["arguments"],
                "output": s["output"],
                "duration_ms": s["duration_ms"],
            }
            for s in self.steps
            if s["kind"] == "tool"
        ]
