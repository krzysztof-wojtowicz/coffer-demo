from datetime import date
from decimal import Decimal

from coffer.analytics.compare import CategoryChange
from coffer.analytics.month import TxView
from coffer.analytics.spending import category_stats, cut_savings, total_change

D = Decimal


def _tx(amount: str, cid: int = 1, name: str = "Jedzenie") -> TxView:
    return TxView(date(2025, 3, 1), D(amount), cid, name, True)


def test_category_stats_only_expenses():
    stats = category_stats([_tx("-10.00"), _tx("-20.01"), _tx("500.00"), _tx("-5", 2, "Zdrowie")])
    assert [s.category_name for s in stats] == ["Jedzenie", "Zdrowie"]
    food = stats[0]
    assert (food.count, food.total, food.average, food.largest) == (
        2,
        D("30.01"),
        D("15.01"),
        D("20.01"),
    )
    assert category_stats([_tx("100")]) == []


def test_total_change():
    changes = [
        CategoryChange(1, "a", D("120.00"), D("100.00"), D("20.00"), D("20.0")),
        CategoryChange(2, "b", D("0.00"), D("50.00"), D("-50.00"), D("-100.0")),
    ]
    t = total_change(changes)
    assert (t.current, t.previous, t.change, t.change_pct) == (
        D("120.00"),
        D("150.00"),
        D("-30.00"),
        D("-20.0"),
    )
    empty = total_change([])
    assert empty.change_pct is None and empty.change == D("0.00")


def test_cut_savings():
    assert cut_savings(D("812.50"), D("10")) == (D("81.25"), D("975.00"))
    assert cut_savings(D("33.33"), D("10")) == (D("3.33"), D("39.96"))
