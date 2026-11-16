from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from coffer.agent.schemas import Finding, Recommendation, ReportDraft
from coffer.agent.validator import Seen, extract_numbers, validate_draft

PORTFOLIO = {
    "total_value": "10000.00",
    "positions": [{"symbol": "AAPL", "share_pct": "50.0"}],
}
LINKS = {"results": [{"title": "Apple", "url": "https://finance.yahoo.com/quote/AAPL"}]}


def seen(*outputs: Any) -> Seen:
    s = Seen()
    for o in outputs:
        s.add(o)
    return s


def draft(**kw: Any) -> ReportDraft:
    base: dict[str, Any] = {
        "headline": "Portfel jest wart 10000.00 PLN.",
        "findings": [
            Finding(title="Wniosek", detail="Pozycja ma 50.0% portfela.", refers_to="portfolio")
        ],
    }
    return ReportDraft(**{**base, **kw})


def test_ok():
    assert validate_draft(draft(), seen(PORTFOLIO)) == []


def test_number_outside_data():
    errs = validate_draft(
        draft(findings=[Finding(title="x", refers_to="calc", value="777777.77")]), seen(PORTFOLIO)
    )
    assert any("777777.77" in e for e in errs)


def test_invented_number_in_prose_is_rejected():
    d = draft(headline="Wartość 777777.77 PLN.")
    assert any("777777.77" in e for e in validate_draft(d, seen(PORTFOLIO)))


def test_years_are_narration():
    assert validate_draft(draft(headline="Od 2024 roku portfel rośnie."), seen(PORTFOLIO)) == []


@pytest.mark.parametrize(
    "text",
    ["Kapitalizacja 5.18 bln USD.", "Kapitalizacja 5177 mld USD.", "Około 5.2 bln USD."],
)
def test_rounded_and_rescaled_numbers_match(text):
    s = seen({"market_cap": "5177380175872.0 USD"})
    f = Finding(title="Kapitalizacja", refers_to="market", value=text)
    assert validate_draft(draft(headline=text, findings=[f]), s) == []


def test_fraction_as_percent_matches():
    s = seen({"dividend_yield": "0.0412"})
    f = Finding(title="Dywidenda", refers_to="market", value="4.12%")
    assert validate_draft(draft(headline="Stopa dywidendy 4.1%.", findings=[f]), s) == []


def test_small_whole_numbers_are_narration():
    d = draft(headline="Masz 3 pozycje i ryzyko 4/5.")
    assert validate_draft(d, seen(PORTFOLIO)) == []


def test_finding_value_is_strict():
    f = Finding(title="x", refers_to="calc", value="42")
    assert validate_draft(draft(findings=[f]), seen(PORTFOLIO)) != []


def test_rounded_integer_matches_data():
    assert validate_draft(draft(headline="Około 10000 PLN."), seen(PORTFOLIO)) == []


def test_numbers_from_context_count_as_seen():
    s = seen(PORTFOLIO, {"fakty": {"Największa pozycja": "62.5"}})
    assert validate_draft(draft(headline="Największa pozycja to 62.5%."), s) == []


def test_symbol_must_come_from_tools():
    rec = Recommendation(title="Kup", symbol="MSFT")
    assert validate_draft(draft(recommendations=[rec]), seen(PORTFOLIO)) != []
    ok = Recommendation(title="Trzymaj", symbol="aapl")
    assert validate_draft(draft(recommendations=[ok]), seen(PORTFOLIO)) == []


def test_url_must_come_from_tools():
    s = seen(PORTFOLIO, LINKS)
    bad = draft(source_urls=["https://evil.example/x"])
    assert validate_draft(bad, s) != []
    good = draft(source_urls=["https://finance.yahoo.com/quote/AAPL"])
    assert validate_draft(good, s) == []
    rec = Recommendation(title="x", source_url="https://evil.example/y")
    assert validate_draft(draft(recommendations=[rec]), s) != []


def test_seen_collects_titles_and_symbols():
    s = seen(LINKS, {"symbols": ["msft"]})
    assert s.titles["https://finance.yahoo.com/quote/AAPL"] == "Apple"
    assert "MSFT" in s.symbols


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 234,50 zł", [Decimal("1234.50")]),
        ("12.5% i 3", [Decimal("12.5"), Decimal("3")]),
        ("brak liczb", []),
    ],
)
def test_extract_numbers(text, expected):
    assert extract_numbers(text) == expected


@given(st.text(max_size=200))
def test_extract_numbers_never_raises(text):
    extract_numbers(text)
