"""Dane demo: konto demo@coffer.local z wymyślonymi transakcjami.

Transakcje obejmują 3 pełne miesiące wstecz oraz bieżący miesiąc do dzisiaj.
Skrypt jest idempotentny: transakcje konta demo są usuwane i tworzone od nowa.

Uruchomienie: `make seed` (wymaga wcześniej `make migrate`).
"""

import calendar
import datetime as dt
import random
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from coffer.accounts.models import User
from coffer.accounts.service import hash_password, register
from coffer.core.db import SessionLocal
from coffer.transactions.models import Category, Transaction

DEMO_EMAIL = "demo@coffer.local"
DEMO_PASSWORD = "demo12345"
SEED = 42

GROCERY_SHOPS = [
    "BIEDRONKA 1234 KRAKÓW",
    "LIDL SP. Z O.O. KRAKÓW",
    "ŻABKA Z1234 KRAKÓW",
    "CARREFOUR EXPRESS TEST KRAKÓW",
    "PIEKARNIA TESTOWA KRAKÓW",
]


@dataclass(frozen=True)
class _Draft:
    date: dt.date
    amount: Decimal
    description: str
    category: str


def _random_amount(rng: random.Random, low_cents: int, high_cents: int) -> Decimal:
    return Decimal(rng.randint(low_cents, high_cents)).scaleb(-2)


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    year_offset, month_index = divmod(year * 12 + (month - 1) + delta, 12)
    return year_offset, month_index + 1


def _month_drafts(rng: random.Random, year: int, month: int) -> list[_Draft]:
    days = calendar.monthrange(year, month)[1]
    label = f"{month:02d}/{year}"

    def on(day: int) -> dt.date:
        return dt.date(year, month, day)

    def random_day() -> dt.date:
        return on(rng.randint(1, days))

    drafts = [
        _Draft(
            on(1),
            Decimal("8500.00"),
            f"PRZELEW PRZYCHODZĄCY WYNAGRODZENIE {label} FIRMA TESTOWA SP. Z O.O.",
            "Wynagrodzenie",
        ),
        _Draft(
            on(2),
            Decimal("-1850.00"),
            f"PRZELEW WYCHODZĄCY CZYNSZ {label} SPÓŁDZIELNIA PRZYKŁADOWA",
            "Mieszkanie",
        ),
        _Draft(
            on(12),
            _random_amount(rng, -26000, -15000),
            "PRZELEW WYCHODZĄCY RACHUNEK ZA PRĄD ENERGIA TESTOWA",
            "Rachunki",
        ),
        _Draft(on(15), Decimal("-69.00"), "PŁATNOŚĆ KARTĄ INTERNET FIBER TEST", "Rachunki"),
        _Draft(on(20), Decimal("-39.99"), "PŁATNOŚĆ BLIK TELEFON MOBILNY TEST", "Rachunki"),
        _Draft(on(8), Decimal("-49.00"), "PŁATNOŚĆ BLIK NETFLIX.COM", "Rozrywka"),
        _Draft(
            on(15),
            Decimal("-1000.00"),
            "PRZELEW WŁASNY NA RACHUNEK OSZCZĘDNOŚCIOWY",
            "Przelewy własne",
        ),
        _Draft(
            on(20),
            Decimal("-500.00"),
            "PRZELEW WYCHODZĄCY DOM MAKLERSKI TESTOWY ZASILENIE RACHUNKU",
            "Inwestycje",
        ),
        _Draft(
            random_day(),
            _random_amount(rng, -28000, -20000),
            "ZAKUP KARTĄ ORLEN STACJA 55 KRAKÓW",
            "Transport",
        ),
    ]
    for _ in range(rng.randint(2, 4)):
        drafts.append(
            _Draft(random_day(), Decimal("-4.60"), "ZAKUP KARTĄ MPK KRAKÓW BILET", "Transport")
        )
    for _ in range(rng.randint(10, 20)):
        shop = rng.choice(GROCERY_SHOPS)
        drafts.append(
            _Draft(
                random_day(),
                _random_amount(rng, -18000, -1200),
                f"ZAKUP KARTĄ {shop}",
                "Jedzenie",
            )
        )
    drafts.append(
        _Draft(
            random_day(),
            _random_amount(rng, -6000, -1500),
            "ZAKUP KARTĄ APTEKA DOZ KRAKÓW",
            "Zdrowie",
        )
    )
    drafts.append(
        _Draft(
            random_day(),
            _random_amount(rng, -25000, -4000),
            "ZAKUP KARTĄ ALLEGRO.PL",
            "Zakupy",
        )
    )
    drafts.append(
        _Draft(
            random_day(),
            _random_amount(rng, -9000, -3000),
            "ZAKUP KARTĄ KINO CINEMA TEST",
            "Rozrywka",
        )
    )
    return drafts


def generate(today: dt.date) -> list[_Draft]:
    rng = random.Random(SEED)
    drafts: list[_Draft] = []
    for back in (3, 2, 1):
        year, month = _shift_month(today.year, today.month, -back)
        drafts.extend(_month_drafts(rng, year, month))
    drafts.extend(_month_drafts(rng, today.year, today.month))
    return sorted((d for d in drafts if d.date <= today), key=lambda d: d.date)


def _demo_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        return register(db, DEMO_EMAIL, DEMO_PASSWORD)
    user.password_hash = hash_password(DEMO_PASSWORD)
    return user


def _category_id(categories: dict[str, int], name: str) -> int:
    try:
        return categories[name]
    except KeyError:
        raise RuntimeError(f"Brak kategorii {name!r} w bazie; uruchom `make migrate`.") from None


def seed_demo(db: Session, today: dt.date | None = None) -> int:
    today = today or dt.date.today()
    user = _demo_user(db)
    categories = {c.name: c.id for c in db.scalars(select(Category))}
    db.execute(delete(Transaction).where(Transaction.user_id == user.id))
    drafts = generate(today)
    db.add_all(
        Transaction(
            user_id=user.id,
            date=d.date,
            amount=d.amount,
            currency="PLN",
            base_amount=d.amount,
            description=d.description,
            category_id=_category_id(categories, d.category),
            source="manual",
        )
        for d in drafts
    )
    db.commit()
    return len(drafts)


def main() -> None:
    with SessionLocal() as db:
        count = seed_demo(db)
    print(f"Konto demo: {DEMO_EMAIL} (hasło: {DEMO_PASSWORD}), transakcji: {count}")


if __name__ == "__main__":
    main()
