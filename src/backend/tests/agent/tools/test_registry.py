import pytest
from pydantic import BaseModel

from coffer.agent.tools.registry import (
    Tool,
    ToolArgumentError,
    ToolCall,
    ToolContext,
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


ECHO = Tool(name="echo", description="Powtarza tekst", input_model=EchoIn, func=_echo)


@pytest.fixture
def ctx(db, user) -> ToolContext:
    return ToolContext(db=db, user_id=user.id)


def test_call_returns_toolcall(ctx):
    reg = ToolRegistry()
    reg.register(ECHO, ["t"])
    res = reg.call("echo", {"text": "ab", "times": 2}, ctx)
    assert isinstance(res, ToolCall)
    assert res.name == "echo"
    assert res.arguments == {"text": "ab", "times": 2}
    assert res.output == {"result": "abab"}
    assert res.duration_ms >= 0


def test_unknown_tool(ctx):
    with pytest.raises(UnknownTool):
        ToolRegistry().call("nope", {}, ctx)


@pytest.mark.parametrize("args", [{}, {"text": "a", "times": "xx"}, {"times": 2}])
def test_bad_arguments(ctx, args):
    reg = ToolRegistry()
    reg.register(ECHO, ["t"])
    with pytest.raises(ToolArgumentError):
        reg.call("echo", args, ctx)


def test_toolset_membership():
    reg = ToolRegistry()
    other = Tool(name="other", description="Inne", input_model=EchoIn, func=_echo)
    reg.register(ECHO, ["a", "b"])
    reg.register(other, ["b"])
    assert [t.name for t in reg.toolset("a")] == ["echo"]
    assert sorted(t.name for t in reg.toolset("b")) == ["echo", "other"]


def test_schemas_format():
    reg = ToolRegistry()
    reg.register(ECHO, ["t"])
    schemas = reg.schemas(reg.toolset("t"))
    assert schemas == [
        {
            "type": "function",
            "function": {
                "name": "echo",
                "description": "Powtarza tekst",
                "parameters": EchoIn.model_json_schema(),
            },
        }
    ]


def test_default_registry_user_data():
    reg = default_registry()
    tools = reg.toolset("user_data")
    assert sorted(t.name for t in tools) == ["get_investment_profile", "get_month_analysis"]
    schemas = reg.schemas(tools)
    assert all(s["type"] == "function" and s["function"]["description"] for s in schemas)
    month = next(s for s in schemas if s["function"]["name"] == "get_month_analysis")
    assert "month" in month["function"]["parameters"]["properties"]
    assert "user_id" not in str(schemas)
