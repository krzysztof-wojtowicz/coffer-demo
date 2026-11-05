import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ToolContext:
    db: Session
    user_id: int  # never comes from the model (F02)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    func: Callable[[ToolContext, Any], BaseModel]


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    output: dict[str, Any]
    duration_ms: int


class UnknownTool(Exception):
    pass


class ToolArgumentError(Exception):
    pass


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._toolsets: dict[str, list[Tool]] = {}

    def register(self, tool: Tool, toolsets: list[str]) -> None:
        self._tools[tool.name] = tool
        for name in toolsets:
            self._toolsets.setdefault(name, []).append(tool)

    def toolset(self, name: str) -> list[Tool]:
        return list(self._toolsets.get(name, []))

    def schemas(self, tools: list[Tool]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_model.model_json_schema(),
                },
            }
            for t in tools
        ]

    def call(self, name: str, arguments: dict[str, Any], ctx: ToolContext) -> ToolCall:
        tool = self._tools.get(name)
        if tool is None:
            raise UnknownTool(name)
        try:
            parsed = tool.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise ToolArgumentError(str(exc)) from exc
        start = time.perf_counter()
        result = tool.func(ctx, parsed)
        duration_ms = int((time.perf_counter() - start) * 1000)
        return ToolCall(
            name=name,
            arguments=dict(arguments),
            output=result.model_dump(mode="json"),
            duration_ms=duration_ms,
        )


def default_registry() -> ToolRegistry:
    from coffer.agent.tools.user_data import (
        GET_INVESTMENT_PROFILE,
        GET_MONTH_ANALYSIS,
    )

    registry = ToolRegistry()
    registry.register(GET_MONTH_ANALYSIS, ["user_data"])
    registry.register(GET_INVESTMENT_PROFILE, ["user_data"])
    return registry
