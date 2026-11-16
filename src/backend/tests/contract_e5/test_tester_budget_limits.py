"""Black-box contract tests for E5-02 (limits + insights API). Written from the card."""

from datetime import date
from decimal import Decimal

import pytest

MONEY_KEYS_INSIGHTS = {
    "comparison": ["current", "previous", "change"],
    "top_growth": ["current", "average_3m", "increase"],
    "limits": ["limit", "spent", "remaining"],
}


def _is_money_str(v) -> bool:
    return isinstance(v, str) and Decimal(v) == Decimal(v).quantize(Decimal("0.01"))


def test_limits_require_auth(client):
    assert client.get("/api/budget/limits").status_code == 401
    assert client.put("/api/budget/limits/1", json={"amount": "10.00"}).status_code == 401
    assert client.delete("/api/budget/limits/1").status_code == 401
    assert client.get("/api/budget/2025-03/insights").status_code == 401


def test_limits_route_before_month(auth_client):
    r = auth_client.get("/api/budget/limits")
    assert r.status_code == 200
    assert r.json() == []


def test_put_get_delete_limit(auth_client, budget_cats):
    cat = budget_cats[0]
    r = auth_client.put(f"/api/budget/limits/{cat.id}", json={"amount": "500.00"})
    assert r.status_code == 200
    assert r.json() == {"category_id": cat.id, "category_name": cat.name, "amount": "500.00"}
    # upsert
    r = auth_client.put(f"/api/budget/limits/{cat.id}", json={"amount": "750.5"})
    assert r.status_code == 200
    assert Decimal(r.json()["amount"]) == Decimal("750.50")
    items = auth_client.get("/api/budget/limits").json()
    assert len(items) == 1 and _is_money_str(items[0]["amount"])
    assert auth_client.delete(f"/api/budget/limits/{cat.id}").status_code == 204
    assert auth_client.get("/api/budget/limits").json() == []


def test_limits_sorted_by_name(auth_client, budget_cats):
    for c in budget_cats[:3]:
        auth_client.put(f"/api/budget/limits/{c.id}", json={"amount": "100.00"})
    names = [i["category_name"] for i in auth_client.get("/api/budget/limits").json()]
    assert names == sorted(names)
    assert len(names) == 3


def test_put_unknown_category_404(auth_client):
    r = auth_client.put("/api/budget/limits/999999", json={"amount": "10.00"})
    assert r.status_code == 404
    assert r.json()["detail"] == "Nie znaleziono kategorii"


def test_put_non_budget_category_422(auth_client, non_budget_cat):
    if non_budget_cat is None:
        pytest.skip("no non-budget category seeded")
    r = auth_client.put(f"/api/budget/limits/{non_budget_cat.id}", json={"amount": "10.00"})
    assert r.status_code == 422
    assert r.json()["detail"] == "Limit można ustawić tylko dla kategorii budżetowej"


@pytest.mark.parametrize(
    "amount", ["0", "0.00", "-5.00", "10.123", "1000000000000.00", "abc", "", None]
)
def test_put_invalid_amount_422(auth_client, budget_cats, amount):
    r = auth_client.put(f"/api/budget/limits/{budget_cats[0].id}", json={"amount": amount})
    assert r.status_code == 422


def test_put_max_amount_ok(auth_client, budget_cats):
    r = auth_client.put(
        f"/api/budget/limits/{budget_cats[0].id}", json={"amount": "999999999999.99"}
    )
    assert r.status_code == 200
    assert r.json()["amount"] == "999999999999.99"


def test_delete_missing_limit_404(auth_client, budget_cats):
    r = auth_client.delete(f"/api/budget/limits/{budget_cats[0].id}")
    assert r.status_code == 404
    assert r.json()["detail"] == "Nie ustawiono limitu dla tej kategorii"


def test_limits_isolated_between_users(auth_client, other_auth_client, budget_cats):
    cat = budget_cats[0]
    assert (
        auth_client.put(f"/api/budget/limits/{cat.id}", json={"amount": "100.00"}).status_code
        == 200
    )
    assert other_auth_client.get("/api/budget/limits").json() == []
    # other user cannot delete it
    assert other_auth_client.delete(f"/api/budget/limits/{cat.id}").status_code == 404
    assert len(auth_client.get("/api/budget/limits").json()) == 1
    # other user's PUT does not overwrite mine
    other_auth_client.put(f"/api/budget/limits/{cat.id}", json={"amount": "5.00"})
    assert auth_client.get("/api/budget/limits").json()[0]["amount"] == "100.00"


def test_insights_isolated_from_other_user_data(
    auth_client, other_auth_client, user, make_user, db, budget_cats, add_tx
):
    from sqlalchemy import select

    from coffer.accounts.models import User

    other = db.scalars(select(User).where(User.email == "other@example.com")).one()
    cat = budget_cats[0]
    add_tx(other, date(2025, 3, 5), "-999.00", cat.id)
    other_auth_client.put(f"/api/budget/limits/{cat.id}", json={"amount": "10.00"})
    r = auth_client.get("/api/budget/2025-03/insights")
    assert r.status_code == 200
    body = r.json()
    assert body["comparison"] == [] and body["top_growth"] == [] and body["limits"] == []


def test_insights_empty_month_shape(auth_client):
    r = auth_client.get("/api/budget/2025-03/insights")
    assert r.status_code == 200
    assert r.json() == {
        "month": "2025-03",
        "previous_month": "2025-02",
        "comparison": [],
        "top_growth": [],
        "limits": [],
    }


@pytest.mark.parametrize("bad", ["2025-13", "abc", "2025-3"])
def test_insights_bad_month_422(auth_client, bad):
    assert auth_client.get(f"/api/budget/{bad}/insights").status_code == 422


def test_previous_month_crosses_year(auth_client):
    assert auth_client.get("/api/budget/2025-01/insights").json()["previous_month"] == "2024-12"


def test_insights_no_history_zero_average_and_null_pct(auth_client, user, budget_cats, add_tx):
    cat = budget_cats[0]
    add_tx(user, date(2025, 3, 5), "-120.50", cat.id)
    body = auth_client.get("/api/budget/2025-03/insights").json()
    assert len(body["comparison"]) == 1
    c = body["comparison"][0]
    assert c["category_id"] == cat.id and c["category_name"] == cat.name
    assert c["current"] == "120.50" and c["previous"] == "0.00"
    assert c["change"] == "120.50" and c["change_pct"] is None
    g = body["top_growth"][0]
    assert g["average_3m"] == "0.00" and g["increase"] == "120.50"
    assert g["increase_pct"] is None


def test_insights_comparison_values_and_sorting(auth_client, user, budget_cats, add_tx):
    a, b, c = budget_cats[:3]
    add_tx(user, date(2025, 2, 5), "-100.00", a.id)
    add_tx(user, date(2025, 3, 5), "-150.00", a.id)  # +50 (50.0%)
    add_tx(user, date(2025, 2, 6), "-300.00", b.id)
    add_tx(user, date(2025, 3, 6), "-100.00", b.id)  # -200 (-66.7%)
    add_tx(user, date(2025, 2, 7), "-30.00", c.id)  # dropped category: -30
    body = auth_client.get("/api/budget/2025-03/insights").json()
    rows = {r["category_id"]: r for r in body["comparison"]}
    assert set(rows) == {a.id, b.id, c.id}
    assert rows[a.id]["change"] == "50.00" and rows[a.id]["change_pct"] == "50.0"
    assert rows[b.id]["change"] == "-200.00" and rows[b.id]["change_pct"] == "-66.7"
    assert rows[c.id]["current"] == "0.00" and rows[c.id]["change"] == "-30.00"
    order = [r["category_id"] for r in body["comparison"]]
    assert order == [b.id, a.id, c.id]  # by |change| desc
    for key in ("current", "previous", "change"):
        assert all(_is_money_str(r[key]) for r in body["comparison"])


def test_insights_top_growth_vs_3m_average(auth_client, user, budget_cats, add_tx):
    a = budget_cats[0]
    add_tx(user, date(2024, 12, 5), "-30.00", a.id)
    add_tx(user, date(2025, 1, 5), "-60.00", a.id)
    # Feb: nothing (counts as 0) -> average (30+60+0)/3 = 30.00
    add_tx(user, date(2025, 3, 5), "-90.00", a.id)
    g = auth_client.get("/api/budget/2025-03/insights").json()["top_growth"]
    assert len(g) == 1
    assert g[0]["average_3m"] == "30.00"
    assert g[0]["increase"] == "60.00"
    assert g[0]["increase_pct"] == "200.0"


def test_insights_top_growth_max3_budget_only_positive(
    auth_client, user, budget_cats, non_budget_cat, add_tx
):
    assert len(budget_cats) >= 5
    for i, c in enumerate(budget_cats[:5]):
        add_tx(user, date(2025, 3, 5), f"-{(i + 1) * 100}.00", c.id)
    if non_budget_cat is not None:
        add_tx(user, date(2025, 3, 5), "-9999.00", non_budget_cat.id)
    # one category that fell: not growth
    add_tx(
        user,
        date(2025, 2, 5),
        "-5000.00",
        budget_cats[5].id if len(budget_cats) > 5 else budget_cats[0].id,
    )
    g = auth_client.get("/api/budget/2025-03/insights").json()["top_growth"]
    assert len(g) <= 3
    ids = {c.id for c in budget_cats}
    assert all(x["category_id"] in ids for x in g)
    assert all(Decimal(x["increase"]) > 0 for x in g)
    incs = [Decimal(x["increase"]) for x in g]
    assert incs == sorted(incs, reverse=True)


def test_insights_comparison_sum_equals_expenses(auth_client, user, budget_cats, add_tx):
    amounts = ["-0.01", "-33.33", "-100.10", "-7.77"]
    for c, amt in zip(budget_cats, amounts, strict=False):
        add_tx(user, date(2025, 3, 9), amt, c.id)
    add_tx(user, date(2025, 3, 1), "5000.00", budget_cats[0].id)
    month = auth_client.get("/api/budget/2025-03").json()
    body = auth_client.get("/api/budget/2025-03/insights").json()
    total = sum(Decimal(r["current"]) for r in body["comparison"])
    assert total == Decimal(month["expenses"])


def test_insights_limits_status(auth_client, user, budget_cats, add_tx):
    a, b, c = budget_cats[:3]
    add_tx(user, date(2025, 3, 5), "-150.00", a.id)
    add_tx(user, date(2025, 3, 6), "-40.00", b.id)
    auth_client.put(f"/api/budget/limits/{a.id}", json={"amount": "100.00"})
    auth_client.put(f"/api/budget/limits/{b.id}", json={"amount": "200.00"})
    auth_client.put(f"/api/budget/limits/{c.id}", json={"amount": "50.00"})  # no spending
    rows = {
        r["category_id"]: r
        for r in auth_client.get("/api/budget/2025-03/insights").json()["limits"]
    }
    assert rows[a.id]["exceeded"] is True
    assert rows[a.id]["spent"] == "150.00" and rows[a.id]["limit"] == "100.00"
    assert rows[a.id]["remaining"] in ("-50.00", "0.00")  # contract: remaining; negative or clamped
    assert Decimal(rows[a.id]["used_pct"]) == Decimal("150")
    assert rows[b.id]["exceeded"] is False and rows[b.id]["spent"] == "40.00"
    assert rows[b.id]["remaining"] == "160.00"
    assert rows[c.id]["spent"] == "0.00" and rows[c.id]["exceeded"] is False
    for r in rows.values():
        assert isinstance(r["used_pct"], str)
        assert all(_is_money_str(r[k]) for k in ("limit", "spent", "remaining"))


def test_limit_exactly_reached_not_exceeded(auth_client, user, budget_cats, add_tx):
    a = budget_cats[0]
    add_tx(user, date(2025, 3, 5), "-100.00", a.id)
    auth_client.put(f"/api/budget/limits/{a.id}", json={"amount": "100.00"})
    row = auth_client.get("/api/budget/2025-03/insights").json()["limits"][0]
    assert row["exceeded"] is False  # spent > limit is strict


def test_month_endpoint_shape_unchanged_with_limits(auth_client, budget_cats):
    auth_client.put(f"/api/budget/limits/{budget_cats[0].id}", json={"amount": "100.00"})
    r = auth_client.get("/api/budget/2025-03")
    assert r.status_code == 200
    assert set(r.json()) == {"month", "income", "expenses", "balance", "surplus", "by_category"}
