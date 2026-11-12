import datetime as dt
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy import text

from coffer.analytics.net_worth import cash_amounts, cash_balance
from coffer.core.clock import today
from tests.budget.test_net_worth import URL as NW
from tests.budget.test_net_worth import add_tx
from tests.portfolio.test_portfolio_api import fake_market

URL = "/api/cash/opening-balance"
TODAY = today()


def test_requires_auth(client):
    assert client.get(URL).status_code == 401
    assert client.put(URL, json={"amount": "1.00", "as_of": TODAY.isoformat()}).status_code == 401
    assert client.delete(URL).status_code == 401


def test_crud(auth_client):
    assert auth_client.get(URL).json() is None
    r = auth_client.put(URL, json={"amount": "-1200.5", "as_of": TODAY.isoformat()})
    assert r.status_code == 200
    assert r.json() == {"amount": "-1200.50", "as_of": TODAY.isoformat()}
    auth_client.put(URL, json={"amount": "10", "as_of": "2026-01-01"})
    assert auth_client.get(URL).json() == {"amount": "10.00", "as_of": "2026-01-01"}
    assert auth_client.delete(URL).status_code == 204
    assert auth_client.delete(URL).status_code == 204
    assert auth_client.get(URL).json() is None


@pytest.mark.parametrize(
    "body",
    [
        {"amount": "1.234", "as_of": TODAY.isoformat()},
        {"amount": "abc", "as_of": TODAY.isoformat()},
        {"amount": "1e12", "as_of": TODAY.isoformat()},
        {"amount": "NaN", "as_of": TODAY.isoformat()},
        {"amount": "1.00", "as_of": (TODAY + dt.timedelta(days=1)).isoformat()},
        {"amount": "1.00"},
    ],
)
def test_validation_422(auth_client, body):
    assert auth_client.put(URL, json=body).status_code == 422


def test_future_date_message_polish(auth_client):
    r = auth_client.put(URL, json={"amount": "1.00", "as_of": "2999-01-01"})
    assert "przyszłości" in r.text


def test_isolation(auth_client, other_auth_client):
    auth_client.put(URL, json={"amount": "100.00", "as_of": TODAY.isoformat()})
    assert other_auth_client.get(URL).json() is None
    other_auth_client.put(URL, json={"amount": "5.00", "as_of": TODAY.isoformat()})
    other_auth_client.delete(URL)
    assert auth_client.get(URL).json()["amount"] == "100.00"


def test_cascade_on_user_delete(auth_client, db, user):
    auth_client.put(URL, json={"amount": "100.00", "as_of": TODAY.isoformat()})
    db.execute(text("DELETE FROM users WHERE id = :i"), {"i": user.id})
    db.commit()
    assert db.execute(text("SELECT count(*) FROM opening_balances")).scalar() == 0


def test_cash_uses_opening_balance(auth_client, db, user, category_id, monkeypatch):
    fake_market(monkeypatch, {})
    cat = category_id("Inne")
    own = category_id("Przelewy własne")
    d = TODAY - dt.timedelta(days=10)
    add_tx(db, user, d - dt.timedelta(days=5), "-700.00", cat)  # before: inside opening
    add_tx(db, user, d, "-300.00", cat)  # same day: inside opening
    add_tx(db, user, d + dt.timedelta(days=1), "100.00", cat)
    add_tx(db, user, TODAY, "-40.25", own)  # out-of-budget category still counts
    add_tx(db, user, TODAY + dt.timedelta(days=1), "999.00", cat)  # future
    assert auth_client.get(NW).json()["cash_balance"] == "-940.25"
    assert auth_client.get(NW).json()["opening_balance_set"] is False
    auth_client.put(URL, json={"amount": "2000.00", "as_of": d.isoformat()})
    b = auth_client.get(NW).json()
    assert b["cash_balance"] == "2059.75"
    assert b["opening_balance_set"] is True
    auth_client.delete(URL)
    assert auth_client.get(NW).json()["cash_balance"] == "-940.25"


def test_regression_cash_counts_out_of_budget_and_ignores_month_filter(
    auth_client, db, user, category_id, monkeypatch
):
    """Cash must equal the sum of ALL transactions,."""
    fake_market(monkeypatch, {})
    add_tx(db, user, TODAY, "1000.00", category_id("Inne"))
    add_tx(db, user, TODAY, "-300.00", category_id("Inwestycje"))
    assert auth_client.get(NW).json()["cash_balance"] == "700.00"
    month = auth_client.get(f"/api/budget/{TODAY:%Y-%m}").json()
    assert month["balance"] == "700.00"
    assert month["surplus"] == "1000.00"


amounts = st.decimals(min_value=-(10**6), max_value=10**6, places=2)
days = st.integers(min_value=-60, max_value=60)


@given(opening=amounts, as_of=days, rows=st.lists(st.tuples(days, amounts), max_size=30))
def test_cash_property(opening, as_of, rows):
    today = dt.date(2026, 6, 1)
    base = lambda n: today + dt.timedelta(days=n)  # noqa: E731
    dated = [(base(n), a) for n, a in rows]
    got = cash_balance(cash_amounts(dated, today, base(as_of)), opening)
    expected = opening + sum((a for n, a in rows if as_of < n <= 0), Decimal(0))
    assert got == expected


def test_no_opening_sums_everything_until_today():
    today = dt.date(2026, 6, 1)
    dated = [
        (dt.date(2000, 1, 1), Decimal("5")),
        (today, Decimal("-2")),
        (dt.date(2027, 1, 1), Decimal("9")),
    ]
    assert cash_balance(cash_amounts(dated, today)) == Decimal("3.00")


def test_balance_dated_warsaw_today_accepted_at_utc_evening(auth_client, monkeypatch):
    # 23:30 UTC on 2026-06-10 is already 2026-06-11 in Warsaw (CEST): not a future date.
    import coffer.core.clock as clock

    class FakeDT(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 6, 10, 23, 30, tzinfo=dt.UTC).astimezone(tz)

    monkeypatch.setattr(clock.dt, "datetime", FakeDT)
    ok = auth_client.put(URL, json={"amount": "5", "as_of": "2026-06-11"})
    assert ok.status_code == 200
    too_far = auth_client.put(URL, json={"amount": "5", "as_of": "2026-06-12"})
    assert too_far.status_code == 422
