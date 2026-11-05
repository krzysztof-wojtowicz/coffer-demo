from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from coffer.accounts.models import User
from coffer.analytics.month import TxView
from coffer.transactions import service
from coffer.transactions.models import Category, Transaction
from coffer.transactions.schemas import TransactionCreate


def _create(db, user_id, d, amount, desc="x", category_id=None):
    return service.create(
        db,
        user_id,
        TransactionCreate(
            date=d, amount=Decimal(amount), description=desc, category_id=category_id
        ),
    )


def test_list_categories_sorted(db: Session):
    cats = service.list_categories(db)
    names = [c.name for c in cats]
    assert names == sorted(names)
    assert sum(c.is_default for c in cats) == 1


def test_create_and_list_for_user(db: Session, user: User):
    tx = _create(db, user.id, date(2026, 3, 10), "-45.50")
    assert tx.id
    assert tx.base_amount == Decimal("-45.50")
    assert tx.source == "manual"
    assert tx.currency == "PLN"
    rows = service.list_for_user(db, user.id, "2026-03")
    assert [r.id for r in rows] == [tx.id]
    assert service.list_for_user(db, user.id, "2026-04") == []
    assert len(service.list_for_user(db, user.id, None)) == 1


def test_delete_returns_bool(db: Session, user: User, make_user):
    other = make_user(email="o@example.com")
    tx = _create(db, user.id, date(2026, 3, 10), "5")
    assert service.delete(db, other.id, tx.id) is False
    assert service.delete(db, user.id, tx.id) is True
    assert service.delete(db, user.id, tx.id) is False


def test_list_views_range_and_user(db: Session, user: User, make_user):
    other = make_user(email="o@example.com")
    _create(db, user.id, date(2026, 2, 28), "-1")
    inside_a = _create(db, user.id, date(2026, 3, 1), "-10.10")
    _create(db, user.id, date(2026, 3, 31), "20.20")
    _create(db, user.id, date(2026, 4, 1), "-3")
    _create(db, other.id, date(2026, 3, 15), "-99")
    views = service.list_views(db, user.id, date(2026, 3, 1), date(2026, 4, 1))
    assert len(views) == 2
    assert all(isinstance(v, TxView) for v in views)
    assert {v.base_amount for v in views} == {Decimal("-10.10"), Decimal("20.20")}
    v = next(v for v in views if v.date == date(2026, 3, 1))
    default = db.query(Category).filter(Category.is_default).one()
    assert v.category_id == default.id == db.get(Transaction, inside_a.id).category_id
    assert v.category_name == default.name
    assert v.in_budget == default.in_budget


def test_list_views_in_budget_flag(db: Session, user: User):
    cat = db.query(Category).filter(Category.in_budget.is_(False)).first()
    if cat is None:
        return
    _create(db, user.id, date(2026, 3, 5), "-7", category_id=cat.id)
    views = service.list_views(db, user.id, date(2026, 3, 1), date(2026, 4, 1))
    assert views[0].in_budget is False
    assert views[0].category_name == cat.name
