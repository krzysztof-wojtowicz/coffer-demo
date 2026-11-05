import asyncio
from collections.abc import Awaitable
from typing import Any

from mcp import types

from coffer.market import service
from coffer.market.mcp_server import build_server
from coffer.market.tools import MARKET_TOOLS


def _run[T](awaitable: Awaitable[T]) -> T:
    async def _main() -> T:
        return await awaitable

    return asyncio.run(_main())


def _list_tools() -> dict[str, types.Tool]:
    server = build_server()
    handler = server._mcp_server.request_handlers[types.ListToolsRequest]
    result = _run(handler(types.ListToolsRequest(method="tools/list")))
    assert isinstance(result.root, types.ListToolsResult)
    return {t.name: t for t in result.root.tools}


def _call(name: str, args: dict[str, Any]) -> types.CallToolResult:
    server = build_server()
    handler = server._mcp_server.request_handlers[types.CallToolRequest]
    req = types.CallToolRequest(
        method="tools/call", params=types.CallToolRequestParams(name=name, arguments=args)
    )
    result = _run(handler(req)).root
    assert isinstance(result, types.CallToolResult)
    return result


def _text(result: types.CallToolResult) -> str:
    return "".join(c.text for c in result.content if isinstance(c, types.TextContent))


def test_tools_list_uses_shared_schemas():
    tools = _list_tools()
    assert set(tools) == {t.name for t in MARKET_TOOLS}
    for t in MARKET_TOOLS:
        assert tools[t.name].inputSchema == t.parameters
        assert tools[t.name].description == t.description
    assert tools["get_quotes"].inputSchema["properties"]["symbols"]["maxItems"] == 20
    limit = tools["get_market_tips"].inputSchema["properties"]["limit"]
    assert limit["minimum"] == 1 and limit["maximum"] == 20


def test_call_quotes(fake_yf):
    result = _call("get_quotes", {"symbols": ["aapl", "ZZZZ"]})
    assert not result.isError
    assert result.structuredContent is not None
    assert result.structuredContent["quotes"][0]["price"] == "190.13"
    assert "190.13" in _text(result)


def test_invalid_args_is_error(fake_yf):
    result = _call("get_quotes", {"symbols": "AAPL"})
    assert result.isError
    assert "musi być listą" in _text(result)
    assert fake_yf.quote_calls == []


def test_unknown_tool_is_error():
    result = _call("nope", {})
    assert result.isError and "Nieznane narzędzie" in _text(result)


def test_limit_clamped(monkeypatch):
    seen: list[int] = []

    def fake_tips(limit: int = 5) -> list[service.MarketTip]:
        seen.append(limit)
        return []

    monkeypatch.setattr(service, "get_market_tips", fake_tips)
    result = _call("get_market_tips", {"limit": 1000})
    assert not result.isError and seen == [20]
