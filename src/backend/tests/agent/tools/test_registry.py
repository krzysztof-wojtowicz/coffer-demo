from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from coffer.agent.tools.registry import (
    Tool,
    ToolArgumentError,
    ToolCall,
    ToolContext,
    ToolFailure,
    ToolRegistry,
    UnknownTool,
    default_registry,
)


class EchoIn(BaseModel):
    text: str
    times: int = 1


class EchoOut(BaseModel):
    result: str


def _echo(ctx: ToolContext, args: EchoIn) -> EchoOut:
    return EchoOut(result=args.text * args.times)


def _fail(ctx: ToolContext, args: EchoIn) -> EchoOut:
    raise ToolFailure("Nie ma danych.")


def _crash(ctx: ToolContext, args: EchoIn) -> EchoOut:
    raise KeyError("internal detail")


ECHO = Tool(name="echo", description="Powtarza tekst", input_model=EchoIn, func=_echo, group="calc")


@pytest.fixture
def ctx(db, user) -> ToolContext:
    return ToolContext(db=db, user_id=user.id, now=datetime.now(UTC))


def make(*tools: Tool) -> ToolRegistry:
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)
    return reg


def test_call_returns_toolcall(ctx):
    res = make(ECHO).call("echo", {"text": "ab", "times": 2}, ctx)
    assert isinstance(res, ToolCall)
    assert res.name == "echo" and res.arguments == {"text": "ab", "times": 2}
    assert res.output == {"result": "abab"}
    assert res.status == "ok" and res.error is None and res.duration_ms >= 0


def test_unknown_tool(ctx):
    with pytest.raises(UnknownTool):
        ToolRegistry().call("nope", {}, ctx)


@pytest.mark.parametrize("args", [{}, {"text": "a", "times": "xx"}, {"times": 2}])
def test_bad_arguments(ctx, args):
    with pytest.raises(ToolArgumentError):
        make(ECHO).call("echo", args, ctx)


def test_tool_failure_becomes_error_output(ctx):
    tool = Tool("fail", "Błąd", EchoIn, _fail, group="calc")
    res = make(tool).call("fail", {"text": "a"}, ctx)
    assert res.status == "error" and res.error == "Nie ma danych."
    assert res.output == {"error": "Nie ma danych."}


def test_unexpected_exception_is_generic_and_does_not_leak(ctx):
    tool = Tool("crash", "Wyjątek", EchoIn, _crash, group="market", uses_internet=True)
    res = make(tool).call("crash", {"text": "a"}, ctx)
    assert res.status == "error"
    assert "internal detail" not in str(res.output) and res.output["error"]


def test_describe():
    tool = Tool("net", "Sieć", EchoIn, _echo, group="market", uses_internet=True)
    described = make(ECHO, tool).describe()
    assert [d["name"] for d in described] == ["echo", "net"]
    assert described[0] == {
        "name": "echo",
        "description": "Powtarza tekst",
        "group": "calc",
        "uses_internet": False,
        "parameters": EchoIn.model_json_schema(),
    }
    assert described[1]["group"] == "market" and described[1]["uses_internet"] is True


def test_default_registry_catalogue():
    reg = default_registry()
    described = {d["name"]: d for d in reg.describe()}
    assert len(described) >= 20
    for name in ("get_month_analysis", "get_portfolio", "get_net_worth", "target_allocation"):
        assert name in described
    assert described["target_allocation"]["group"] == "calc"
    assert described["get_portfolio"]["group"] == "user_data"
    assert described["get_quotes"]["group"] == "market"
    assert described["get_quotes"]["uses_internet"] is True
    assert all(d["description"] for d in described.values())
    assert all(
        d["uses_internet"] is (d["group"] == "market")
        for d in described.values()
        if d["name"] != "get_instrument_universe"
    )
    assert "user_id" not in str(described)
    month = described["get_month_analysis"]["parameters"]
    assert "month" in month["properties"]


def test_catalog_validation_is_enforced():
    from coffer.agent.actions.catalog import validate_catalog

    assert validate_catalog(default_registry()) == []


def test_actions_only_reference_registered_tools():
    from coffer.agent.actions.catalog import ACTIONS

    names = set(default_registry().names())
    for action in ACTIONS.values():
        assert set(action.tools) <= names, action.id
