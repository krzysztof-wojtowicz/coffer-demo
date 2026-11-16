from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from coffer.analytics.compare import CategoryChange, CategoryGrowth
from coffer.analytics.limits import LimitStatus
from coffer.analytics.month import MonthSummary


class CategoryTotalOut(BaseModel):
    category_id: int
    category_name: str
    expenses: str


class MonthSummaryOut(BaseModel):
    month: str
    income: str
    expenses: str
    balance: str
    surplus: str
    by_category: list[CategoryTotalOut]

    @classmethod
    def from_summary(cls, s: MonthSummary) -> "MonthSummaryOut":
        def fmt(v: Decimal) -> str:
            return f"{v:.2f}"

        return cls(
            month=s.month,
            income=fmt(s.income),
            expenses=fmt(s.expenses),
            balance=fmt(s.balance),
            surplus=fmt(s.surplus),
            by_category=[
                CategoryTotalOut(
                    category_id=c.category_id,
                    category_name=c.category_name,
                    expenses=fmt(c.expenses),
                )
                for c in s.by_category
            ],
        )


class NetWorthOut(BaseModel):
    cash_balance: str
    portfolio_value: str
    net_worth: str
    portfolio_complete: bool
    opening_balance_set: bool = False
    as_of: date


def _money(v: Decimal) -> str:
    return f"{v:.2f}"


def _pct(v: Decimal | None) -> str | None:
    return None if v is None else f"{v:.1f}"


class LimitIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2, le=Decimal("999999999999.99"))


class LimitOut(BaseModel):
    category_id: int
    category_name: str
    amount: str

    @classmethod
    def build(cls, category_id: int, category_name: str, amount: Decimal) -> "LimitOut":
        return cls(category_id=category_id, category_name=category_name, amount=_money(amount))


class CategoryChangeOut(BaseModel):
    category_id: int
    category_name: str
    current: str
    previous: str
    change: str
    change_pct: str | None

    @classmethod
    def from_change(cls, c: CategoryChange) -> "CategoryChangeOut":
        return cls(
            category_id=c.category_id,
            category_name=c.category_name,
            current=_money(c.current),
            previous=_money(c.previous),
            change=_money(c.change),
            change_pct=_pct(c.change_pct),
        )


class CategoryGrowthOut(BaseModel):
    category_id: int
    category_name: str
    current: str
    average_3m: str
    increase: str
    increase_pct: str | None

    @classmethod
    def from_growth(cls, g: CategoryGrowth) -> "CategoryGrowthOut":
        return cls(
            category_id=g.category_id,
            category_name=g.category_name,
            current=_money(g.current),
            average_3m=_money(g.average_3m),
            increase=_money(g.increase),
            increase_pct=_pct(g.increase_pct),
        )


class LimitStatusOut(BaseModel):
    category_id: int
    category_name: str
    limit: str
    spent: str
    remaining: str
    used_pct: str
    exceeded: bool

    @classmethod
    def from_status(cls, s: LimitStatus) -> "LimitStatusOut":
        return cls(
            category_id=s.category_id,
            category_name=s.category_name,
            limit=_money(s.limit),
            spent=_money(s.spent),
            remaining=_money(s.remaining),
            used_pct=_pct(s.used_pct) or "0.0",
            exceeded=s.exceeded,
        )


class InsightsOut(BaseModel):
    month: str
    previous_month: str
    comparison: list[CategoryChangeOut]
    top_growth: list[CategoryGrowthOut]
    limits: list[LimitStatusOut]
