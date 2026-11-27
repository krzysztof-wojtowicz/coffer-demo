# Market-data MCP server (`coffer-market`)

`coffer.market` exposes Yahoo Finance data (`yfinance`) as an MCP server over stdio. Tool definitions live in `coffer/market/tools.py`. Agent actions in the API (`POST /api/agent/actions/{id}/run`) do not use this server: they have their own tools in `coffer/agent/tools/market_data.py` (e.g. `get_quotes`, `get_instrument_universe`) built on the same `coffer.market.service` (quotes cached in `market_quotes`, refreshed by `make prices`).

| Tool | Arguments | Returns |
|---|---|---|
| `get_quotes` | `symbols: list[str]` (max 20) | quotes: price and % change as strings, currency, `as_of` |
| `get_market_tips` | `limit: int = 5` | market news (title, summary, publisher, URL) |
| `get_instrument_universe` | none | candidates across asset classes with a risk level 1–5 |

Data is cached in memory for about 5 minutes. The tools receive no user data.

## Running

```bash
make setup          # installs yfinance and mcp
make mcp-market     # = cd src/backend && uv run python -m coffer.market.mcp_server
```

The server talks over stdin/stdout, so on its own in a terminal it just waits for a client.

## Claude Code

From the repository root:

```bash
claude mcp add coffer-market -- uv run --directory "$(pwd)/src/backend" python -m coffer.market.mcp_server
```

Check with `claude mcp list` or `/mcp` in a session.

## Claude Desktop

In `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`), add (with your own absolute path):

```json
{
  "mcpServers": {
    "coffer-market": {
      "command": "uv",
      "args": ["run", "--directory", "/ABSOLUTE/PATH/coffer/src/backend", "python", "-m", "coffer.market.mcp_server"]
    }
  }
}
```

Restart Claude Desktop and the tools appear in its tool list. If `uv` isn't on the app's `PATH`, give its full path (`which uv`).

## Notes
- The `mcp` package is pinned to `<2` (in 2.x `FastMCP` was renamed `MCPServer`).
- Market data is informational only; it is not investment advice.
