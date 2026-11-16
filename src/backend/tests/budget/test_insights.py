from datetime import date

from tests.budget.test_budget_api import add_tx  # noqa: F401


def test_insights(auth_client, user, add_tx, category_id):  # noqa: F811
    food, tr = category_id("Jedzenie"), category_id("Transport")
    add_tx(user, date(2026, 3, 2), "-300.00", food)
    add_tx(user, date(2026, 3, 3), "-50.00", tr)
    add_tx(user, date(2026, 2, 3), "-100.00", food)
    add_tx(user, date(2026, 1, 3), "-100.00", food)
    add_tx(user, date(2025, 12, 3), "-100.00", food)
    auth_client.put(f"/api/budget/limits/{food}", json={"amount": "250.00"})
    auth_client.put(f"/api/budget/limits/{tr}", json={"amount": "250.00"})
    body = auth_client.get("/api/budget/2026-03/insights").json()
    assert body["previous_month"] == "2026-02"
    assert body["comparison"][0] == {
        "category_id": food,
        "category_name": "Jedzenie",
        "current": "300.00",
        "previous": "100.00",
        "change": "200.00",
        "change_pct": "200.0",
    }
    assert body["comparison"][1]["change_pct"] is None
    growth = {g["category_name"]: g for g in body["top_growth"]}
    assert growth["Jedzenie"]["average_3m"] == "100.00"
    assert growth["Transport"]["average_3m"] == "0.00"
    assert growth["Transport"]["increase_pct"] is None
    lim = {x["category_name"]: x for x in body["limits"]}
    assert lim["Jedzenie"]["exceeded"] is True and lim["Jedzenie"]["used_pct"] == "120.0"
    assert lim["Jedzenie"]["remaining"] == "-50.00"
    assert lim["Transport"]["exceeded"] is False
