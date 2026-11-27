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


class CategoryChangeOut(_Out):
    category_id: int
    category_name: str
    current: MoneyStr
    previous: MoneyStr
    change: MoneyStr
    change_pct: PctStr | None


class CategoryGrowthOut(_Out):
    category_id: int
    category_name: str
    current: MoneyStr
    average_3m: MoneyStr
    increase: MoneyStr
    increase_pct: PctStr | None


class InsightsOut(_Out):
    month: str
    previous_month: str
    comparison: list[CategoryChangeOut]
    top_growth: list[CategoryGrowthOut]
