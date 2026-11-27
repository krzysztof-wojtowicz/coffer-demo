"""Portfolio valuation: pure functions, no database, no HTTP.

All amounts are Decimal; money is rounded with `quantize` (2 places, half-up),
percentages are rounded half-up to 0.1.

Every amount is converted to the base currency (PLN) with rates passed in by the caller
(`fx_to_pln`: currency -> PLN per 1 unit). Rules when a rate is missing:
- missing rate for the quote currency: the market price is ignored and the holding falls
  back to the manual value / purchase cost (converted with the holding-currency rate);
- missing rate for the holding currency: the holding cannot be expressed in PLN at all.
  It is reported in its own currency (`converted=False`, `share_pct=None`) and excluded
  from totals and allocation. A market price is used only if quoted in that same currency.
Each currency without a rate is listed in `PortfolioSummary.fx_missing`.
"""

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Literal

from coffer.analytics.shares import category_shares
from coffer.core.money import ZERO, quantize

TENTH = Decimal("0.1")
ONE = Decimal("1")
BASE_CURRENCY = "PLN"

ValueSource = Literal["market", "manual", "cost"]


@dataclass(frozen=True)
class HoldingInput:
    id: int
    name: str
    symbol: str | None
    asset_class: str
    quantity: Decimal
    purchase_price: Decimal  # per unit, in `currency`
    manual_value: Decimal | None = None  # total, in `currency`
    market_price: Decimal | None = None  # per unit, in `price_currency`
    currency: str = BASE_CURRENCY
    price_currency: str | None = None  # None = same as `currency`
    purchase_date: dt.date | None = None
    created_at: dt.datetime | None = None


@dataclass(frozen=True)
class HoldingValuation:
    id: int
    name: str
    symbol: str | None
    asset_class: str
    quantity: Decimal
    cost_basis: Decimal
    current_value: Decimal
    value_source: ValueSource
    market_price: Decimal | None
    price_currency: str | None
    gain: Decimal
    gain_pct: Decimal | None
    share_pct: Decimal | None
    amount_currency: str  # currency of cost_basis/current_value/gain (PLN unless not converted)
    converted: bool


@dataclass(frozen=True)
class ClassAllocation:
    asset_class: str
    value: Decimal
    share_pct: Decimal


@dataclass(frozen=True)
class PositionLot:
    """One holding inside a position; amounts in the holding's own currency."""

    holding_id: int
    purchase_date: dt.date | None
    quantity: Decimal
    purchase_price: Decimal
    currency: str
    cost: Decimal
    value: Decimal
    value_source: ValueSource
    gain: Decimal
    gain_pct: Decimal | None


@dataclass(frozen=True)
class PositionValuation:
    """Holdings sharing a ticker. PLN amounts are None when any lot has no FX rate."""

    key: str
    symbol: str | None
    name: str
    asset_class: str
    quantity: Decimal
    cost: Decimal | None
    value: Decimal | None
    gain: Decimal | None
    gain_pct: Decimal | None
    share_pct: Decimal | None
    avg_price: Decimal | None
    latest_purchase_date: dt.date | None
    lots: list[PositionLot]


@dataclass(frozen=True)
class PortfolioSummary:
    holdings: list[HoldingValuation]
    positions: list[PositionValuation]
    allocation: list[ClassAllocation]
    total_value: Decimal
    total_cost: Decimal
    total_gain: Decimal
    total_gain_pct: Decimal | None
    fx_missing: list[str]


def gain_pct(gain: Decimal, cost: Decimal) -> Decimal | None:
    """Gain relative to cost in %, 0.1 precision; None when cost is zero."""
    if cost == 0:
        return None
    return (gain * 100 / cost).quantize(TENTH, rounding=ROUND_HALF_UP)


def fx_rate(currency: str, fx_to_pln: Mapping[str, Decimal]) -> Decimal | None:
    if currency == BASE_CURRENCY:
        return ONE
    return fx_to_pln.get(currency)


@dataclass(frozen=True)
class _Valued:
    cost: Decimal
    value: Decimal
    source: ValueSource
    converted: bool
    missing: frozenset[str]


def value_holding(h: HoldingInput, fx_to_pln: Mapping[str, Decimal] | None = None) -> _Valued:
    """Cost and current value of one holding, in PLN when the holding currency has a rate."""
    fx = fx_to_pln or {}
    missing: set[str] = set()
    holding_rate = fx_rate(h.currency, fx)
    converted = holding_rate is not None
    if holding_rate is None:
        missing.add(h.currency)
    rate = holding_rate if holding_rate is not None else ONE
    cost = quantize(h.purchase_price * h.quantity * rate)

    if h.market_price is not None:
        price_ccy = h.price_currency or h.currency
        if converted:
            price_rate = fx_rate(price_ccy, fx)
        else:
            price_rate = ONE if price_ccy == h.currency else None
        if price_rate is None:
            missing.add(price_ccy)
        else:
            value = quantize(h.market_price * h.quantity * price_rate)
            return _Valued(cost, value, "market", converted, frozenset(missing))
    if h.manual_value is not None:
        return _Valued(
            cost, quantize(h.manual_value * rate), "manual", converted, frozenset(missing)
        )
    return _Valued(cost, cost, "cost", converted, frozenset(missing))


def value_holding_native(
    h: HoldingInput, fx_to_pln: Mapping[str, Decimal] | None = None
) -> tuple[Decimal, Decimal, ValueSource]:
    """Cost, value and value source of one holding in its own currency."""
    fx = fx_to_pln or {}
    cost = quantize(h.purchase_price * h.quantity)
    if h.market_price is not None:
        price_ccy = h.price_currency or h.currency
        if price_ccy == h.currency:
            return cost, quantize(h.market_price * h.quantity), "market"
        price_rate, own_rate = fx_rate(price_ccy, fx), fx_rate(h.currency, fx)
        if price_rate is not None and own_rate is not None:
            value = quantize(h.market_price * h.quantity * price_rate / own_rate)
            return cost, value, "market"
    if h.manual_value is not None:
        return cost, quantize(h.manual_value), "manual"
    return cost, cost, "cost"


def _position(
    key: str,
    group: Sequence[tuple[HoldingInput, _Valued]],
    total_value: Decimal,
    fx: Mapping[str, Decimal] | None,
) -> PositionValuation:
    newest = max(
        (h for h, _ in group),
        key=lambda h: (
            h.purchase_date is not None,
            h.purchase_date or dt.date.min,
            h.created_at is not None,
            h.created_at.timestamp() if h.created_at else 0,
            h.id,
        ),
    )
    lots = []
    for h, _ in sorted(
        group,
        key=lambda hv: (hv[0].purchase_date is None, hv[0].purchase_date or dt.date.min, hv[0].id),
    ):
        cost, value, source = value_holding_native(h, fx)
        lots.append(
            PositionLot(
                holding_id=h.id,
                purchase_date=h.purchase_date,
                quantity=h.quantity,
                purchase_price=h.purchase_price,
                currency=h.currency,
                cost=cost,
                value=value,
                value_source=source,
                gain=value - cost,
                gain_pct=gain_pct(value - cost, cost),
            )
        )
    quantity = sum((h.quantity for h, _ in group), ZERO)
    dates = [h.purchase_date for h, _ in group if h.purchase_date]
    cost = value = gain = pct = share = avg = None
    if all(v.converted for _, v in group):
        cost = sum((v.cost for _, v in group), ZERO)
        value = sum((v.value for _, v in group), ZERO)
        gain = value - cost
        pct = gain_pct(gain, cost)
        if total_value != 0:
            share = (value * 100 / total_value).quantize(TENTH, rounding=ROUND_HALF_UP)
        avg = quantize(cost / quantity)
    return PositionValuation(
        key=key,
        symbol=(newest.symbol or "").strip().upper() or None,
        name=newest.name,
        asset_class=newest.asset_class,
        quantity=quantity,
        cost=cost,
        value=value,
        gain=gain,
        gain_pct=pct,
        share_pct=share,
        avg_price=avg,
        latest_purchase_date=max(dates) if dates else None,
        lots=lots,
    )


# Valid inputs reach ~1e24 per holding; the default 28-digit context overflows on sums.
_PRECISION = 60


def portfolio_summary(
    items: Sequence[HoldingInput], fx_to_pln: Mapping[str, Decimal] | None = None
) -> PortfolioSummary:
    with localcontext(prec=_PRECISION):
        return _portfolio_summary(items, fx_to_pln)


def _portfolio_summary(
    items: Sequence[HoldingInput], fx_to_pln: Mapping[str, Decimal] | None
) -> PortfolioSummary:
    valued = [(h, value_holding(h, fx_to_pln)) for h in items]
    included = [(h, v) for h, v in valued if v.converted]

    total_value = quantize(sum((v.value for _, v in included), ZERO))
    total_cost = quantize(sum((v.cost for _, v in included), ZERO))
    total_gain = total_value - total_cost
    shares = dict(
        zip(
            (h.id for h, _ in included),
            category_shares([v.value for _, v in included], total_value),
            strict=True,
        )
    )

    holdings = [
        HoldingValuation(
            id=h.id,
            name=h.name,
            symbol=h.symbol,
            asset_class=h.asset_class,
            quantity=h.quantity,
            cost_basis=v.cost,
            current_value=v.value,
            value_source=v.source,
            market_price=h.market_price,
            price_currency=(h.price_currency or h.currency) if h.market_price is not None else None,
            gain=v.value - v.cost,
            gain_pct=gain_pct(v.value - v.cost, v.cost),
            share_pct=shares.get(h.id) if v.converted else None,
            amount_currency=BASE_CURRENCY if v.converted else h.currency,
            converted=v.converted,
        )
        for h, v in valued
    ]

    by_class: dict[str, Decimal] = {}
    for h, v in included:
        by_class[h.asset_class] = by_class.get(h.asset_class, ZERO) + v.value
    ordered = sorted(by_class.items(), key=lambda kv: (-kv[1], kv[0]))
    class_shares = category_shares([v for _, v in ordered], total_value)
    allocation = [
        ClassAllocation(asset_class=cls, value=quantize(v), share_pct=s)
        for (cls, v), s in zip(ordered, class_shares, strict=True)
    ]

    groups: dict[str, list[tuple[HoldingInput, _Valued]]] = {}
    for h, v in valued:
        sym = (h.symbol or "").strip().upper()
        groups.setdefault(sym or f"id:{h.id}", []).append((h, v))
    positions = sorted(
        (_position(k, g, total_value, fx_to_pln) for k, g in groups.items()),
        key=lambda p: (p.value is None, -(p.value or ZERO), p.key),
    )

    return PortfolioSummary(
        holdings=holdings,
        positions=positions,
        allocation=allocation,
        total_value=total_value,
        total_cost=total_cost,
        total_gain=total_gain,
        total_gain_pct=gain_pct(total_gain, total_cost),
        fx_missing=sorted(set().union(*(v.missing for _, v in valued))),
    )
