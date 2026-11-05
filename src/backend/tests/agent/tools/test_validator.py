from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from coffer.agent.drafts import RationaleItem, SuggestionDraft
from coffer.agent.validator import extract_numbers, validate

from .conftest import make_call

MONTH_OUT = {
    "month": "2025-03",
    "income": "6009.63",
    "expenses": "1000.00",
    "balance": "5009.63",
    "surplus": "5009.63",
    "by_category": [{"category": "Jedzenie", "expenses": "486.00", "share_pct": "48.6"}],
}
MONTH = make_call("get_month_analysis", MONTH_OUT)
PROFILE_OK = make_call("get_investment_profile", {"available": True, "risk": "high"})
PROFILE_NO = make_call("get_investment_profile", {"available": False, "risk": None})


def draft(
    summary="Masz nadwyżkę.", claim="Nadwyżka jest.", refers_to: Any = "budget", value="5009,63"
):
    return SuggestionDraft(
        summary=summary,
        rationale=[RationaleItem(claim=claim, refers_to=refers_to, value=value)],
    )


def test_ok():
    assert validate(draft(), [MONTH]) == []


def test_blank_summary():
    errs = validate(draft(summary="   "), [MONTH])
    assert errs and all(isinstance(e, str) for e in errs)


def test_blank_claim():
    assert validate(draft(claim="  \t"), [MONTH])


def test_profile_requires_available():
    d = draft(refers_to="profile", value="wysoka")
    assert validate(d, [MONTH]) != []
    assert validate(d, [MONTH, PROFILE_NO]) != []
    assert validate(d, [MONTH, PROFILE_OK]) == []


def test_portfolio_always_error():
    d = draft(refers_to="portfolio", value="x")
    assert validate(d, [MONTH, PROFILE_OK]) != []
    assert validate(d, [MONTH, make_call("get_portfolio_summary", {"total": "1.00"})]) == []


def test_value_number_not_in_data():
    errs = validate(draft(value="6000"), [MONTH])
    assert errs and any("6000" in e for e in errs)


@pytest.mark.parametrize(
    "value", ["6009,63", "6 009,63", "6 009,63", "6009.63", "48,6%", "2025", "03"]
)
def test_value_formats_allowed(value):
    assert validate(draft(value=value), [MONTH]) == []


def test_value_small_integer_must_match():
    assert validate(draft(value="5"), [MONTH]) != []


def test_rounding_to_integer_allowed():
    # 6009.63 -> round 6010, trunc 6009
    assert validate(draft(value="6010"), [MONTH]) == []
    assert validate(draft(value="6009"), [MONTH]) == []
    assert validate(draft(value="6011"), [MONTH]) != []
    assert validate(draft(value="6008"), [MONTH]) != []


def test_rounding_half_up():
    call = make_call("get_month_analysis", {"x": "10.50"})
    assert validate(draft(value="11"), [call]) == []
    assert validate(draft(value="10"), [call]) == []
    assert validate(draft(value="12"), [call]) != []


def test_summary_checks_only_money_like_numbers():
    assert validate(draft(summary="W 3 kategoriach, 12 pozycji."), [MONTH]) == []
    assert validate(draft(summary="Wydano 321,45 zł."), [MONTH]) != []
    assert validate(draft(summary="Wydano 700 zł."), [MONTH]) != []
    assert validate(draft(summary="Nadwyżka 5009,63 zł."), [MONTH]) == []


def test_claim_checks_only_money_like_numbers():
    assert validate(draft(claim="Top 3 kategorie"), [MONTH]) == []
    assert validate(draft(claim="Wydatki 321,45"), [MONTH]) != []
    assert validate(draft(claim="Wydatki 700"), [MONTH]) != []


def test_numbers_collected_recursively_from_nested_values():
    call = make_call("t", {"a": [{"b": {"c": ["1 234,50"]}}], "d": 77.5})
    assert validate(draft(value="1234,50"), [call]) == []
    assert validate(draft(value="77,5"), [call]) == []


def test_numbers_from_any_tool_call():
    other = make_call("t2", {"v": "42.42"})
    assert validate(draft(value="42,42"), [MONTH, other]) == []


@pytest.mark.parametrize(
    "text,expected",
    [
        ("6009,63", [Decimal("6009.63")]),
        ("6 009,63", [Decimal("6009.63")]),
        ("6 009,63", [Decimal("6009.63")]),
        ("6009.63", [Decimal("6009.63")]),
        ("48,6%", [Decimal("48.6")]),
        ("2026", [Decimal("2026")]),
        ("brak liczb", []),
    ],
)
def test_extract_numbers(text, expected):
    assert extract_numbers(text) == expected


def test_extract_numbers_multiple():
    assert sorted(extract_numbers("od 10,50 do 20,25")) == [Decimal("10.50"), Decimal("20.25")]


def _formats(d: Decimal) -> list[str]:
    plain = f"{d:.2f}"
    ip, fp = plain.split(".")
    groups = f"{int(ip):,}".replace(",", " ")
    return [
        plain,
        f"{ip},{fp}",
        f"{groups},{fp}",
        f"{groups.replace(' ', chr(0xA0))},{fp}",
        f"Kwota: {ip},{fp} zł",
    ]


@given(st.decimals(min_value=Decimal("0.00"), max_value=Decimal("9999999.99"), places=2))
def test_extract_numbers_hypothesis(d):
    for text in _formats(d):
        assert extract_numbers(text) == [d], text


def test_amount_invented_in_risks_is_rejected():
    calls = [make_call("get_month_analysis", {"surplus": "5009.63"})]
    d = SuggestionDraft(
        summary="Masz nadwyżkę.",
        rationale=[RationaleItem(claim="Nadwyżka.", refers_to="budget", value="5009,63")],
        risks=["Możesz stracić nawet 3000 zł."],
    )
    errors = validate(d, calls)
    assert any("Ryzyko 1" in e and "3000" in e for e in errors)
