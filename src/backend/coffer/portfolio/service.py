import importlib
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from coffer.analytics.portfolio import (
    BASE_CURRENCY,
    HoldingInput,
    PortfolioSummary,
    portfolio_summary,
)
from coffer.portfolio.models import Holding
from coffer.portfolio.schemas import HoldingCreate, HoldingUpdate

log = logging.getLogger(__name__)

MARKET_SERVICE = "coffer.market.service"


def list_for_user(db: Session, user_id: int) -> list[Holding]:
    stmt = select(Holding).where(Holding.user_id == user_id).order_by(Holding.id)
    return list(db.scalars(stmt))


def get(db: Session, user_id: int, holding_id: int) -> Holding | None:
    return db.scalar(select(Holding).where(Holding.id == holding_id, Holding.user_id == user_id))


def create(db: Session, user_id: int, data: HoldingCreate) -> Holding:
    holding = Holding(user_id=user_id, **data.model_dump())
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


def update(db: Session, user_id: int, holding_id: int, data: HoldingUpdate) -> Holding | None:
    holding = get(db, user_id, holding_id)
    if holding is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(holding, field, value)
    db.commit()
    db.refresh(holding)
    return holding


def delete(db: Session, user_id: int, holding_id: int) -> bool:
    holding = get(db, user_id, holding_id)
    if holding is None:
        return False
    db.delete(holding)
    db.commit()
    return True


def _market() -> Any | None:
    """coffer.market.service loaded dynamically: the portfolio must work without it."""
    try:
        return importlib.import_module(MARKET_SERVICE)
    except ImportError:
        return None


@dataclass(frozen=True)
class Price:
    price: Decimal
    currency: str


def fetch_prices(symbols: list[str]) -> dict[str, Price] | None:
    """Market prices (with quote currency) by symbol; None when market data is unavailable.

    A missing module, MarketDataUnavailable or any other provider failure degrades to None.
    """
    market = _market()
    if market is None:
        return None
    if not symbols:
        return {}
    try:
        quotes = market.get_quotes(symbols)
    except Exception:  # MarketDataUnavailable or a provider bug: degrade to no prices
        log.warning("market data unavailable", exc_info=True)
        return None
    return {
        sym: Price(Decimal(str(q.price)), str(q.currency or BASE_CURRENCY).upper())
        for sym, q in quotes.items()
        if q is not None
    }


def fetch_fx_rates(currencies: set[str]) -> dict[str, Decimal]:
    """currency -> PLN rate; currencies without a rate are simply left out."""
    market = _market()
    get_fx_rate = getattr(market, "get_fx_rate", None) if market is not None else None
    rates: dict[str, Decimal] = {}
    if get_fx_rate is None:
        return rates
    for ccy in sorted(currencies - {BASE_CURRENCY}):
        try:
            rate = get_fx_rate(ccy, BASE_CURRENCY)
        except Exception:  # contract says it never raises; stay defensive
            log.warning("fx rate unavailable for %s", ccy, exc_info=True)
            rate = None
        if rate is not None and Decimal(str(rate)) > 0:
            rates[ccy] = Decimal(str(rate))
    return rates


@dataclass(frozen=True)
class SummaryResult:
    summary: PortfolioSummary
    currencies: dict[int, str]
    prices_available: bool


def summary(db: Session, user_id: int) -> SummaryResult:
    holdings = list_for_user(db, user_id)
    symbols = sorted({h.symbol for h in holdings if h.symbol})
    prices = fetch_prices(symbols)
    known = prices or {}
    quoted = {h.id: known.get(h.symbol) for h in holdings if h.symbol}
    currencies = {h.currency for h in holdings} | {p.currency for p in known.values()}
    rates = fetch_fx_rates(currencies)
    inputs = []
    for h in holdings:
        q = quoted.get(h.id)
        inputs.append(
            HoldingInput(
                id=h.id,
                name=h.name,
                symbol=h.symbol,
                asset_class=h.asset_class,
                quantity=h.quantity,
                purchase_price=h.purchase_price,
                manual_value=h.manual_value,
                market_price=q.price if q else None,
                currency=h.currency,
                price_currency=q.currency if q else None,
            )
        )
    return SummaryResult(
        summary=portfolio_summary(inputs, rates),
        currencies={h.id: h.currency for h in holdings},
        prices_available=prices is not None,
    )
