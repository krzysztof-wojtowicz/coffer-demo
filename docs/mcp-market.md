# Serwer MCP danych rynkowych (`coffer-market`)

Moduł `coffer.market` udostępnia dane z Yahoo Finance (biblioteka `yfinance`) jako serwer
MCP po stdio. Te same narzędzia (wspólne definicje w `coffer/market/tools.py`) wykorzystuje
doradca inwestycyjny `POST /api/agent/investment/advice`.

| Narzędzie | Argumenty | Zwraca |
|---|---|---|
| `get_quotes` | `symbols: list[str]` (maks. 20) | notowania: cena i zmiana % jako stringi, waluta, `as_of` |
| `get_market_tips` | `limit: int = 5` | wiadomości rynkowe (tytuł, streszczenie, źródło, URL) |
| `get_instrument_universe` | brak | kandydaci z różnych klas aktywów z poziomem ryzyka 1–5 |

Dane są cache'owane w pamięci przez ok. 5 minut. Narzędzia nie dostają żadnych danych
użytkownika.

## Uruchomienie

```bash
make setup          # instaluje yfinance i mcp
make mcp-market     # = cd src/backend && uv run python -m coffer.market.mcp_server
```

Serwer komunikuje się przez stdin/stdout, więc sam w terminalu tylko czeka na klienta.

## Claude Code

Z katalogu głównego repozytorium:

```bash
claude mcp add coffer-market -- uv run --directory "$(pwd)/src/backend" python -m coffer.market.mcp_server
```

Sprawdzenie: `claude mcp list` albo `/mcp` w sesji.

## Claude Desktop

W `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`) dodaj
(ścieżkę zastąp własną, absolutną):

```json
{
  "mcpServers": {
    "coffer-market": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/ABSOLUTNA/ŚCIEŻKA/coffer-demo/src/backend",
        "python",
        "-m",
        "coffer.market.mcp_server"
      ]
    }
  }
}
```

Po restarcie Claude Desktop narzędzia pojawią się na liście narzędzi. Jeśli `uv` nie jest
w `PATH` aplikacji, podaj pełną ścieżkę (`which uv`).

## Uwagi

- Pakiet `mcp` jest przypięty do `<2` (w 2.x `FastMCP` zmieniło nazwę na `MCPServer`).
- Dane rynkowe służą celom informacyjnym; to nie jest porada inwestycyjna.
