from datetime import date

from pydantic import BaseModel, ConfigDict

from coffer.core.money import MoneyStr, PctStr


class _Out(BaseModel):
    """Built straight from analytics dataclasses; every exposed field is listed explicitly."""

    model_config = ConfigDict(from_attributes=True)


class CategoryTotalOut(_Out):
    category_id: int
    category_name: str
    expenses: MoneyStr


class MonthSummaryOut(_Out):
    month: str
    income: MoneyStr
    expenses: MoneyStr
    balance: MoneyStr
    surplus: MoneyStr
    by_category: list[CategoryTotalOut]


class NetWorthOut(_Out):
    cash_balance: MoneyStr
    portfolio_value: MoneyStr
    net_worth: MoneyStr
    portfolio_complete: bool
    opening_balance_set: bool = False
    as_of: date


class MonthPointOut(_Out):
    month: str
    income: MoneyStr
    expenses: MoneyStr
    balance: MoneyStr
    surplus: MoneyStr
    savings_rate: PctStr | None


class AverageOut(_Out):
    income: MoneyStr
    expenses: MoneyStr
    balance: MoneyStr
    surplus: MoneyStr
    savings_rate: PctStr | None


class ChangeOut(_Out):
    amount: MoneyStr
    pct: PctStr | None


class PointsChangeOut(_Out):
    amount: PctStr  # percentage points


class TrendChangeOut(_Out):
    income: ChangeOut
    expenses: ChangeOut
    balance: ChangeOut
    surplus: ChangeOut
    savings_rate: PointsChangeOut | None


class CategoryTrendOut(_Out):
    category_id: int
    category_name: str
    amounts: list[MoneyStr]
    average: MoneyStr | None
    change: MoneyStr | None
    change_pct: PctStr | None


class TrendOut(_Out):
    month: str
    months: list[MonthPointOut]
    average: AverageOut | None
    change: TrendChangeOut | None
    categories: list[CategoryTrendOut]
