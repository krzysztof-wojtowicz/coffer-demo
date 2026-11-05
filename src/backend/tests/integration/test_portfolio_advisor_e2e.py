"""End-to-end: portfolio holdings -> summary -> investment advisor (agent 4 / tester).

Market data is mocked at `coffer.market.service.get_quotes` (and news fetching), so no
network is used. The LLM is replaced via the `get_llm_client` dependency.
"""

import datetime as dt
import json
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from coffer.agent.investment.schemas import DISCLAIMER
from coffer.agent.llm import LLMUnavailable, OpenAIClient, get_llm_client
from coffer.agent.testing import FakeLLM
from coffer.main import app
from coffer.market import service as market

HOLDINGS = "/api/portfolio/holdings"
SUMMARY = "/api/portfolio/summary"
ADVICE = "/api/agent/investment/advice"
QUOTES = "/api/market/quotes"

STOCK = {
    "name": "Moje akcje Apple SEKRET",
    "symbol": "aapl",
    "asset_class": "stock",
    "quantity": "7.5",
    "purchase_price": "123.45",
    "note": "notatka prywatna",
}
FLAT = {
    "name": "Mieszkanie na Mokotowie",
    "asset_class": "real_estate",
    "quantity": "1",
    "purchase_price": "400000.00",
    "manual_value": "512345.67",
}
DEPOSIT = {
    "name": "Lokata w banku",
    "asset_class": "cash",
    "quantity": "1",
    "purchase_price": "9876.54",
}


@pytest.fixture(autouse=True)
def fake_market(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[list[str]]]:
    calls: list[list[str]] = []

    def get_quotes(symbols: list[str]) -> dict[str, market.Quote]:
        calls.append(list(symbols))
        out: dict[str, market.Quote] = {}
        for s in symbols:
            if s.strip().upper() == "AAPL":
                out["AAPL"] = market.Quote(
                    "AAPL",
                    "Apple Inc.",
                    Decimal("200.00"),
                    "USD",
                    Decimal("1.50"),
                    dt.datetime.now(dt.UTC),
                )
        return out

    def no_news(symbol: str, count: int) -> list[dict[str, Any]]:
        raise ConnectionError("offline in tests")

    def get_fx_rate(from_ccy: str, to_ccy: str) -> Decimal | None:
        if from_ccy == to_ccy:
            return Decimal("1")
        return Decimal("4.00") if (from_ccy, to_ccy) == ("USD", "PLN") else None

    monkeypatch.setattr(market, "get_quotes", get_quotes)
    monkeypatch.setattr(market, "get_fx_rate", get_fx_rate, raising=False)
    monkeypatch.setattr(market, "_fetch_news", no_news)
    market.clear_cache()
    yield calls
    market.clear_cache()


@pytest.fixture
def use_llm() -> Iterator[Any]:
    def _use(llm: Any) -> Any:
        app.dependency_overrides[get_llm_client] = lambda: llm
        return llm

    yield _use
    app.dependency_overrides.pop(get_llm_client, None)


def _add_holdings(c: TestClient) -> list[int]:
    ids = []
    for body in (STOCK, FLAT, DEPOSIT):
        r = c.post(HOLDINGS, json=body)
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    return ids


def _advice_body(summary: dict[str, Any]) -> dict[str, Any]:
    """Same mapping as PortfolioPage.tsx -> AdvisorPanel (symbol, class, qty, value)."""
    return {
        "holdings": [
            {
                "symbol": h["symbol"],
                "asset_class": h["asset_class"],
                "quantity": h["quantity"],
                "current_value": h["current_value"],
            }
            for h in summary["holdings"]
        ]
    }


@pytest.mark.parametrize("llm", ["none", "unavailable"])
def test_e2e_holdings_summary_advice_without_llm(auth_client, use_llm, fake_market, llm):
    use_llm(None if llm == "none" else FakeLLM([LLMUnavailable("down")] * 5))
    _add_holdings(auth_client)

    r = auth_client.get(SUMMARY)
    assert r.status_code == 200
    s = r.json()
    assert fake_market == [["AAPL"]]
    assert s["prices_available"] is True
    by_name = {h["name"]: h for h in s["holdings"]}
    assert by_name[STOCK["name"]]["value_source"] == "market"
    assert by_name[STOCK["name"]]["current_value"] == "6000.00"  # 200 USD * 7.5 * 4.00 PLN/USD
    assert by_name[FLAT["name"]]["value_source"] == "manual"
    assert by_name[DEPOSIT["name"]]["value_source"] == "cost"
    assert s["total_value"] == "528222.21"
    # money and percentages are JSON strings, never numbers
    for key in ("total_value", "total_cost", "total_gain", "total_gain_pct"):
        assert isinstance(s[key], str), key
    for h in s["holdings"]:
        for key in ("quantity", "cost_basis", "current_value", "gain", "share_pct"):
            assert isinstance(h[key], str), key
    for a in s["allocation"]:
        assert isinstance(a["value"], str) and isinstance(a["share_pct"], str)

    r = auth_client.post(ADVICE, json=_advice_body(s))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["llm_used"] is False
    assert body["disclaimer"] == DISCLAIMER
    picks = body["top_picks"]
    assert len(picks) == 3
    for p in picks:
        assert set(p) == {"name", "asset_class", "symbol", "rationale", "risk_level", "source_url"}
        assert isinstance(p["risk_level"], int) and 1 <= p["risk_level"] <= 3  # default profile
        assert p["rationale"]
    assert body["tips"] == []  # news offline -> empty, no error


def test_e2e_llm_receives_only_aggregates(auth_client, user, use_llm):
    picks = [
        {"name": "Vanguard Total World Stock ETF", "asset_class": "etf", "symbol": "VT",
         "rationale": "Dywersyfikacja.", "risk_level": 3},
        {"name": "Vanguard Total Bond Market ETF", "asset_class": "bond", "symbol": "BND",
         "rationale": "Stabilizacja.", "risk_level": 2},
        {"name": "SPDR Gold Shares", "asset_class": "commodity", "symbol": "GLD",
         "rationale": "Ochrona przed inflacją.", "risk_level": 3},
    ]  # fmt: skip
    fake = use_llm(
        FakeLLM(
            [
                json.dumps({"action": "call_tool", "tool": "get_instrument_universe", "args": {}}),
                json.dumps({"action": "final", "answer": {"top_picks": picks}}),
            ]
        )
    )
    ids = _add_holdings(auth_client)
    s = auth_client.get(SUMMARY).json()

    r = auth_client.post(ADVICE, json=_advice_body(s))
    assert r.status_code == 200, r.text
    assert r.json()["llm_used"] is True
    assert len(fake.calls) == 2

    sent = "\n".join(
        [c["system"] for c in fake.calls] + [m.content for c in fake.calls for m in c["messages"]]
    )
    forbidden = [
        user.email,
        STOCK["name"],
        FLAT["name"],
        DEPOSIT["name"],
        STOCK["note"],
        "6000.00",  # current values
        "512345.67",
        "9876.54",
        "528222.21",  # total
        "123.45",  # purchase price
        "7.5",  # quantity
    ]
    for value in forbidden:
        assert value not in sent, f"leaked to LLM: {value!r}"
    # first user message is the context: only class shares, symbols and profile
    ctx = json.loads(fake.calls[0]["messages"][0].content.split("\n", 1)[1])
    assert set(ctx) == {"profil_ryzyka", "portfel"}
    assert set(ctx["portfel"]) == {"udzialy_klas_pct", "symbole"}
    assert ctx["portfel"]["symbole"] == ["AAPL"]
    assert '"id"' not in fake.calls[0]["messages"][0].content
    for hid in ids:
        assert f'"{hid}"' not in sent


def test_advice_accepts_frontend_shapes(auth_client, use_llm):
    """Edge values the portfolio summary can produce (8-dp quantity, no symbol, zero value)."""
    use_llm(None)
    body = {
        "holdings": [
            {"symbol": None, "asset_class": "crypto", "quantity": "0.12345678",
             "current_value": "0.00"},
            {"symbol": "PKO.WA", "asset_class": "stock", "quantity": "999999999999",
             "current_value": "999999999999.99"},
        ]
    }  # fmt: skip
    r = auth_client.post(ADVICE, json=body)
    assert r.status_code == 200, r.text
    assert len(r.json()["top_picks"]) == 3


@pytest.mark.parametrize(
    ("method", "url", "body"),
    [
        ("get", HOLDINGS, None),
        ("post", HOLDINGS, STOCK),
        ("patch", f"{HOLDINGS}/1", {"name": "X"}),
        ("delete", f"{HOLDINGS}/1", None),
        ("get", SUMMARY, None),
        ("get", f"{QUOTES}?symbols=AAPL", None),
        ("post", ADVICE, {"holdings": []}),
    ],
)
def test_new_endpoints_require_login(client, method, url, body):
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)(url, **kwargs).status_code == 401


def test_foreign_holding_is_404_and_untouched(auth_client, other_auth_client):
    hid = _add_holdings(auth_client)[0]
    assert other_auth_client.patch(f"{HOLDINGS}/{hid}", json={"name": "X"}).status_code == 404
    assert other_auth_client.delete(f"{HOLDINGS}/{hid}").status_code == 404
    other_summary = other_auth_client.get(SUMMARY).json()
    assert other_summary["holdings"] == [] and other_summary["total_value"] == "0.00"
    mine = auth_client.get(HOLDINGS).json()
    assert [h["name"] for h in mine][0] == STOCK["name"]
    assert len(mine) == 3


def test_status_reports_configured_provider(auth_client, use_llm, monkeypatch):
    import coffer.agent.llm as llm_module

    probed: list[str] = []

    def fake_get(url: str, **kwargs: Any) -> Any:  # no network: status probe is mocked
        probed.append(url)
        return type("Resp", (), {"status_code": 200})()

    monkeypatch.setattr(llm_module.httpx, "get", fake_get)
    monkeypatch.setattr(llm_module, "_STATUS_CACHE", {})
    use_llm(OpenAIClient("sk-test", "gpt-4o-mini", "https://api.openai.com/v1", 5))
    r = auth_client.get("/api/agent/status")
    assert r.status_code == 200
    assert r.json()["provider"] == "openai"
