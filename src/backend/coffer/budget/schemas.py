from datetime import date
from decimal import Decimal

from pydantic import BaseModel

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
