"""Demo data: the demo@coffer.local account with made-up transactions and holdings.

Fixed dates (not relative to today): opening balance on 2026-09-01, transactions from
September to DEMO_END. Idempotent: the demo account's data is deleted and recreated.

Run with `make seed` (after `make migrate`).
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
from coffer.cash import service as cash_service
from coffer.cash.schemas import OpeningBalanceIn
from coffer.core.db import SessionLocal
from coffer.portfolio import service as portfolio_service
from coffer.portfolio.schemas import HoldingCreate
from coffer.profile import service as profile_service
from coffer.profile.schemas import ProfileIn
from coffer.transactions.models import Category, Transaction

DEMO_EMAIL = "demo@coffer.local"
DEMO_PASSWORD = "coffer-demo-2026"
DEMO_NAME = "Demo"
SEED = 42
OPENING = OpeningBalanceIn(amount=Decimal("5000.00"), as_of=dt.date(2026, 9, 1))
MONTHS = ((2026, 9), (2026, 10), (2026, 11))
DEMO_END = dt.date(2026, 11, 27)  # no transactions after this day

# Purchase prices are real daily closes from Yahoo Finance (yfinance, fetched 2026-11-27),
# in each instrument's quote currency. Current values come from live quotes, not from here.
HOLDINGS = [
    HoldingCreate(
        name="Vanguard FTSE All-World",
        symbol="VWCE.DE",
        asset_class="etf",
        quantity=Decimal("20"),
        purchase_price=Decimal("166.62"),
        currency="EUR",
        purchase_date=dt.date(2026, 9, 1),
    ),
    HoldingCreate(
        name="iShares Core MSCI World",
        symbol="EUNL.DE",
        asset_class="etf",
        quantity=Decimal("30"),
        purchase_price=Decimal("128.81"),
        currency="EUR",
        purchase_date=dt.date(2026, 10, 1),
    ),
    HoldingCreate(
        name="PKO BP",
        symbol="PKO.WA",
        asset_class="stock",
        quantity=Decimal("100"),
        purchase_price=Decimal("120.30"),
        currency="PLN",
        purchase_date=dt.date(2026, 9, 15),
    ),
    HoldingCreate(
        name="CD Projekt",
        symbol="CDR.WA",
        asset_class="stock",
        quantity=Decimal("15"),
        purchase_price=Decimal("254.50"),
        currency="PLN",
        purchase_date=dt.date(2026, 10, 1),
    ),
    HoldingCreate(
        name="Apple",
        symbol="AAPL",
        asset_class="stock",
        quantity=Decimal("8"),
        purchase_price=Decimal("342.00"),
        currency="USD",
        purchase_date=dt.date(2026, 10, 15),
    ),
    HoldingCreate(
        name="Bitcoin",
        symbol="BTC-USD",
        asset_class="crypto",
        quantity=Decimal("0.05"),
        purchase_price=Decimal("84853.10"),
        currency="USD",
        purchase_date=dt.date(2026, 10, 1),
    ),
    HoldingCreate(
        name="SPDR Gold Shares",
        symbol="GLD",
        asset_class="commodity",
        quantity=Decimal("6"),
        purchase_price=Decimal("394.15"),
        currency="USD",
        purchase_date=dt.date(2026, 9, 15),
    ),
    HoldingCreate(  # no market quote: valued by hand
        name="Obligacje skarbowe EDO",
        asset_class="bond",
        quantity=Decimal("10"),
        purchase_price=Decimal("100.00"),
        currency="PLN",
        purchase_date=dt.date(2026, 9, 1),
        manual_value=Decimal("1030.00"),
    ),
]
PROFILE = ProfileIn(
    horizon="long",
    risk="medium",
    preferred_classes=["stock", "etf", "bond", "commodity", "crypto", "cash"],
)

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


def generate() -> list[_Draft]:
    rng = random.Random(SEED)
    drafts: list[_Draft] = []
    for year, month in MONTHS:
        drafts.extend(_month_drafts(rng, year, month))
    drafts.append(
        _Draft(dt.date(2026, 10, 5), Decimal("-1299.00"), "ZAKUP KARTĄ MEDIA EXPERT", "Zakupy")
    )
    drafts.append(_Draft(dt.date(2026, 11, 10), Decimal("420.00"), "PRZELEW ZWROT PODATKU", "Inne"))
    return sorted((d for d in drafts if d.date <= DEMO_END), key=lambda d: d.date)


def _demo_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        return register(db, DEMO_EMAIL, DEMO_PASSWORD, DEMO_NAME)
    user.password_hash = hash_password(DEMO_PASSWORD)
    user.display_name = DEMO_NAME
    return user


def _category_id(categories: dict[str, int], name: str) -> int:
    try:
        return categories[name]
    except KeyError:
        raise RuntimeError(f"Brak kategorii {name!r} w bazie; uruchom `make migrate`.") from None


def seed_demo(db: Session) -> int:
    user = _demo_user(db)
    categories = {c.name: c.id for c in db.scalars(select(Category))}
    db.execute(delete(Transaction).where(Transaction.user_id == user.id))
    for holding in portfolio_service.list_for_user(db, user.id):
        db.delete(holding)
    drafts = generate()
    db.add_all(
        Transaction(
            user_id=user.id,
            date=d.date,
            amount=d.amount,
            description=d.description,
            category_id=_category_id(categories, d.category),
            source="manual",
        )
        for d in drafts
    )
    db.commit()
    cash_service.upsert(db, user.id, OPENING)
    profile_service.upsert(db, user.id, PROFILE)
    for holding in HOLDINGS:
        portfolio_service.create(db, user.id, holding)
    return len(drafts)


def main() -> None:
    with SessionLocal() as db:
        count = seed_demo(db)
    print(f"Konto demo: {DEMO_EMAIL} (hasło: {DEMO_PASSWORD}), transakcji: {count}")


if __name__ == "__main__":
    main()
