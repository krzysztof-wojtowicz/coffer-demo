"""MCP server exposing Coffer market data tools over stdio.

Run: `python -m coffer.market.mcp_server` (from src/backend) or `make mcp-market`.
Tool schemas and validation come from the shared definitions in `coffer.market.tools`,
so MCP clients see exactly the same limits as the investment advisor.
"""

from functools import partial
from typing import Any

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.types import Tool as MCPTool

from coffer.market.tools import MARKET_TOOLS, call_tool


class MarketMCP(FastMCP):
    async def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(name=t.name, description=t.description, inputSchema=dict(t.parameters))
            for t in MARKET_TOOLS
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        # ToolError (Polish message) propagates and is returned as isError=true.
        return await anyio.to_thread.run_sync(partial(call_tool, name, arguments or {}))


def build_server() -> MarketMCP:
    return MarketMCP("coffer-market")


def main() -> None:
    build_server().run("stdio")


if __name__ == "__main__":
    main()
