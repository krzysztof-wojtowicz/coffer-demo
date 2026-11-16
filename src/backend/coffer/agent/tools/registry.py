import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

ToolGroup = Literal["user_data", "market", "calc"]
TOOL_ERROR = "Narzędzie nie zadziałało. Spróbuj ponownie albo użyj innych danych."


@dataclass(frozen=True)
class ToolContext:
    db: Session
    user_id: int  # never comes from the model (F02)
    now: datetime


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    func: Callable[[ToolContext, Any], BaseModel]
    group: ToolGroup
    uses_internet: bool = False


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    output: dict[str, Any]
    duration_ms: int
    status: Literal["ok", "error"] = "ok"
    error: str | None = None


class ToolFailure(Exception):
    """A tool failed with a user-presentable (Polish) message."""


class UnknownTool(Exception):
    pass


class ToolArgumentError(Exception):
    pass


class ToolRegistry:
    """The single catalogue of agent tools; each action whitelists the names its model may call."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def describe(self) -> list[dict[str, Any]]:
        """Public description of every tool (GET /api/agent/tools)."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "group": t.group,
                "uses_internet": t.uses_internet,
                "parameters": t.input_model.model_json_schema(),
            }
            for t in self._tools.values()
        ]

    def call(self, name: str, arguments: dict[str, Any], ctx: ToolContext) -> ToolCall:
        """Run a tool. Unknown tool / bad arguments raise; a failing tool does not: it yields
        `{"error": "<message>"}` with status "error" so the action goes on."""
        tool = self._tools.get(name)
        if tool is None:
            raise UnknownTool(name)
        try:
            parsed = tool.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise ToolArgumentError(str(exc)) from exc
        start = time.perf_counter()
        try:
            output = tool.func(ctx, parsed).model_dump(mode="json")
            error = None
        except Exception as exc:
            log.warning("Tool %s failed", name, exc_info=True)
            error = str(exc) if isinstance(exc, ToolFailure) else TOOL_ERROR
            output = {"error": error}
        duration_ms = int((time.perf_counter() - start) * 1000)
        return ToolCall(
            name=name,
            arguments=dict(arguments),
            output=output,
            duration_ms=duration_ms,
            status="error" if error else "ok",
            error=error,
        )


def default_registry() -> ToolRegistry:
    from coffer.agent.tools import calc, market_data, user_data

    registry = ToolRegistry()
    for tool in (
        user_data.GET_MONTH_ANALYSIS,
        user_data.GET_INVESTMENT_PROFILE,
        user_data.GET_PORTFOLIO,
        user_data.GET_NET_WORTH,
        user_data.GET_MONTHS_OVERVIEW,
        user_data.GET_SPENDING_INSIGHTS,
        user_data.GET_TRANSACTION_STATS,
        user_data.GET_CATEGORY_LIMITS,
        calc.TARGET_ALLOCATION,
        calc.SIMULATE_PURCHASE,
        calc.COMPOUND_INTEREST,
        calc.SAVINGS_GOAL_PLAN,
        calc.PROPOSE_BUDGET,
        market_data.GET_QUOTES,
        market_data.GET_FX_RATE,
        market_data.GET_PRICE_HISTORY,
        market_data.GET_COMPANY_PROFILE,
        market_data.GET_COMPANY_NEWS,
        market_data.GET_MARKET_NEWS,
        market_data.SEARCH_SYMBOL,
        market_data.GET_WIKIPEDIA_SUMMARY,
        market_data.GET_INSTRUMENT_UNIVERSE,
    ):
        registry.register(tool)
    return registry
