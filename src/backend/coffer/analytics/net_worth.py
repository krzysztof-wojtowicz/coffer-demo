"""Net worth: pure functions, no database, no HTTP."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from coffer.analytics.portfolio import PortfolioSummary
from coffer.core.money import ZERO, quantize


@dataclass(frozen=True)
class NetWorth:
    cash_balance: Decimal
    portfolio_value: Decimal
    net_worth: Decimal
    portfolio_complete: bool
    opening_balance_set: bool = False


def cash_amounts(
    dated: Iterable[tuple[date, Decimal]], today: date, as_of: date | None = None
) -> list[Decimal]:
    """Amounts counted in cash: dated after `as_of` (already in the opening balance) up to today."""
    return [a for d, a in dated if d <= today and (as_of is None or d > as_of)]


def cash_balance(base_amounts: Iterable[Decimal], opening: Decimal = ZERO) -> Decimal:
    return quantize(opening + sum(base_amounts, ZERO))


def portfolio_is_complete(summary: PortfolioSummary, prices_available: bool) -> bool:
    """True when every holding is valued in PLN and quoted symbols use market prices."""
    if summary.fx_missing or not all(h.converted for h in summary.holdings):
        return False
    if any(h.symbol and h.value_source != "market" for h in summary.holdings):
        return False
    return prices_available or not any(h.symbol for h in summary.holdings)


def net_worth(
    base_amounts: Iterable[Decimal],
    portfolio_value: Decimal,
    portfolio_complete: bool,
    opening: Decimal | None = None,
) -> NetWorth:
    cash = cash_balance(base_amounts, opening or ZERO)
    value = quantize(portfolio_value)
    return NetWorth(cash, value, quantize(cash + value), portfolio_complete, opening is not None)
