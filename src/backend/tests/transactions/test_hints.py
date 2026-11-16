from datetime import date
from decimal import Decimal

from coffer.transactions import service
from coffer.transactions.models import Transaction


def _add(db, user, day, desc, cat, review=False):
    db.add(
        Transaction(
            user_id=user.id,
            date=day,
            amount=Decimal("-1.00"),
            currency="PLN",
            base_amount=Decimal("-1.00"),
            description=desc,
            category_id=cat,
            source="manual",
            needs_review=review,
        )
    )
    db.commit()


def test_category_hints_newest_wins_and_skips_review(db, user, make_user, category_id):
    food, shop, other = category_id("Jedzenie"), category_id("Zakupy"), category_id("Inne")
    _add(db, user, date(2026, 1, 1), "Sklep  U Zosi", food)
    _add(db, user, date(2026, 2, 1), "SKLEP U ZOSI", shop)
    _add(db, user, date(2026, 3, 1), "SKLEP U ZOSI", other, review=True)
    stranger = make_user(email="x@example.com")
    _add(db, stranger, date(2026, 4, 1), "OBCY", food)
    assert service.category_hints(db, user.id) == {"sklep u zosi": "Zakupy"}
