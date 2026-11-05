import pytest
import requests

from coffer.market.tools import MARKET_TOOLS, ToolError, call_tool

NAMES = {"get_quotes", "get_market_tips", "get_instrument_universe"}


def test_shared_definitions():
    assert {t.name for t in MARKET_TOOLS} == NAMES
    assert all(t.parameters["type"] == "object" for t in MARKET_TOOLS)


def test_call_tool(fake_yf):
    out = call_tool("get_quotes", {"symbols": ["AAPL"], "extra": 1})
    assert out["quotes"][0]["price"] == "190.13"
    assert len(call_tool("get_market_tips", {"limit": 1})["tips"]) == 1
    assert call_tool("get_instrument_universe", {})["instruments"]
    fake_yf.fail = requests.exceptions.ConnectionError("down")
    fake_yf.prices = {}
    assert call_tool("get_quotes", {"symbols": ["XYZ"]})["quotes"] == []


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("nope", {}),
        ("get_quotes", {}),
        ("get_quotes", {"symbols": "AAPL"}),
        ("get_market_tips", {"limit": "5"}),
    ],
)
def test_call_tool_rejects(name, args):
    with pytest.raises(ToolError):
        call_tool(name, args)
