"""Market tool definitions shared by the MCP server and the investment advisor agent.

Each tool has a name, a description, a JSON schema of its arguments and a plain function
returning JSON-serialisable data (money as strings).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from coffer.market import service


@dataclass(frozen=True)
class MarketTool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]


def get_quotes(symbols: list[str]) -> dict[str, Any]:
    """Current prices for Yahoo Finance symbols (e.g. AAPL, VT, PKO.WA)."""
    try:
        found = service.get_quotes(symbols[:20])
    except service.MarketDataUnavailable:
        return {"error": "Dane rynkowe są chwilowo niedostępne", "quotes": []}
    return {
        "quotes": [
            {
                "symbol": q.symbol,
                "name": q.name,
                "price": str(q.price),
                "currency": q.currency,
                "change_pct": None if q.change_pct is None else str(q.change_pct),
                "as_of": q.as_of.isoformat(),
            }
            for q in found.values()
        ]
    }


def get_market_tips(limit: int = 5) -> dict[str, Any]:
    """Recent market news from investment sources."""
    return {
        "tips": [
            {
                "title": t.title,
                "summary": t.summary,
                "source": t.source,
                "url": t.url,
                "published_at": t.published_at.isoformat() if t.published_at else None,
            }
            for t in service.get_market_tips(limit)
        ]
    }


def get_instrument_universe() -> dict[str, Any]:
    """Candidate instruments across asset classes with a 1-5 risk level."""
    return {
        "instruments": [
            {
                "name": i.name,
                "symbol": i.symbol,
                "asset_class": i.asset_class,
                "risk_level": i.risk_level,
                "description": i.description,
            }
            for i in service.get_instrument_universe()
        ]
    }


MARKET_TOOLS: tuple[MarketTool, ...] = (
    MarketTool(
        name="get_quotes",
        description="Zwraca bieżące notowania (cena, waluta, zmiana %) dla symboli Yahoo Finance.",
        parameters={
            "type": "object",
            "properties": {
                "symbols": {"type": "array", "items": {"type": "string"}, "maxItems": 20}
            },
            "required": ["symbols"],
        },
        func=get_quotes,
    ),
    MarketTool(
        name="get_market_tips",
        description="Zwraca najnowsze wiadomości rynkowe ze źródeł inwestycyjnych.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
        },
        func=get_market_tips,
    ),
    MarketTool(
        name="get_instrument_universe",
        description=(
            "Zwraca listę kandydatów do inwestycji z różnych klas aktywów "
            "(akcje, ETF, obligacje, nieruchomości, surowce, krypto, gotówka) "
            "i poziomem ryzyka 1-5."
        ),
        parameters={"type": "object", "properties": {}},
        func=get_instrument_universe,
    ),
)

TOOLS_BY_NAME = {t.name: t for t in MARKET_TOOLS}


class ToolError(Exception):
    pass


def call_tool(name: str, args: dict[str, Any]) -> Any:
    """Validate arguments loosely and run a market tool. Raises ToolError on bad input."""
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        raise ToolError(f"Nieznane narzędzie: {name}")
    allowed = tool.parameters.get("properties", {})
    clean = {k: v for k, v in (args or {}).items() if k in allowed}
    if name == "get_quotes":
        symbols = clean.get("symbols")
        if not isinstance(symbols, list) or not all(isinstance(s, str) for s in symbols):
            raise ToolError("Argument symbols musi być listą napisów")
    if name == "get_market_tips" and "limit" in clean:
        limit = clean["limit"]
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise ToolError("Argument limit musi być liczbą całkowitą")
        clean["limit"] = max(1, min(limit, 20))
    return tool.func(**clean)
