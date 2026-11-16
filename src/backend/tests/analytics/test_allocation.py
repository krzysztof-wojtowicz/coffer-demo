from decimal import Decimal

import pytest

from coffer.analytics.allocation import (
    HORIZONS,
    RISKS,
    allocation_gap,
    max_position_share,
    share_pct,
    target_allocation,
)

D = Decimal


@pytest.mark.parametrize("risk", RISKS)
@pytest.mark.parametrize("horizon", HORIZONS)
def test_sums_to_100_and_non_negative(risk, horizon):
    target = target_allocation(risk, horizon)
    assert sum(target.values()) == D(100)
    assert all(v > 0 for v in target.values())


def test_medium_medium_is_base():
    assert target_allocation("medium", "medium") == {
        "cash": D("15.0"),
        "bond": D("30.0"),
        "etf": D("30.0"),
        "stock": D("20.0"),
        "real_estate": D("5.0"),
    }


def test_short_horizon_moves_to_cash_from_riskiest():
    t = target_allocation("high", "short")
    assert t["cash"] == D("20.0")
    assert "crypto" not in t  # crypto (5) was taken first, then 10 from stocks
    assert t["stock"] == D("30.0")


def test_long_horizon_moves_to_etf():
    t = target_allocation("low", "long")
    assert t["cash"] == D("20.0") and t["etf"] == D("25.0") and t["bond"] == D("50.0")


def test_riskier_profile_has_more_stocks_and_less_cash():
    low, high = target_allocation("low", "medium"), target_allocation("high", "medium")
    assert high["stock"] > low["stock"] and high["cash"] < low["cash"]


@pytest.mark.parametrize(("risk", "horizon"), [("x", "long"), ("low", "x"), ("", "")])
def test_unknown_input(risk, horizon):
    with pytest.raises(ValueError):
        target_allocation(risk, horizon)


def test_gap_sign_and_order():
    gaps = allocation_gap(
        {"stock": D("60.0"), "cash": D("5.0"), "gold": D("1.0")},
        {"stock": D("20.0"), "cash": D("15.0")},
    )
    assert [g.asset_class for g in gaps] == ["stock", "cash", "gold"]
    assert gaps[0].gap_pp == D("-40.0") and gaps[1].gap_pp == D("10.0")
    assert gaps[2].target_pct == 0 and gaps[2].gap_pp == D("-1.0")


def test_gap_empty():
    assert allocation_gap({}, {}) == []


def test_max_position_share():
    assert max_position_share([D("50"), D("30"), D("20")]) == D("50.0")
    assert max_position_share([D("1"), D("2")]) == D("66.7")  # half-up
    assert max_position_share([]) is None
    assert max_position_share([D("0"), D("0")]) is None


def test_share_pct():
    assert share_pct(D("1"), D("8")) == D("12.5")
    assert share_pct(D("1"), D("16")) == D("6.3")  # half-up
    assert share_pct(D("5"), D("0")) is None
    assert share_pct(D("-5"), D("10")) == D("-50.0")
