"""Deterministic calculation tools (no user data, no network)."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from coffer.agent.tools.registry import Tool, ToolContext
from coffer.analytics.allocation import target_allocation
from coffer.analytics.compare import top_growth
from coffer.analytics.planning import (
    average_by_category,
    average_totals,
    compound_growth,
    monthly_saving_for_goal,
    propose_limits,
)
from coffer.analytics.simulate import ClassValue, simulate_purchase
from coffer.budget import service as budget_service
from coffer.core.months import MonthStr
from coffer.portfolio import service as portfolio_service


class TargetAllocationInput(BaseModel):
    risk: Literal["low", "medium", "high"]
    horizon: Literal["short", "medium", "long"]


class ClassTargetOut(BaseModel):
    asset_class: str
    target_pct: str


class TargetAllocationOut(BaseModel):
    risk: str
    horizon: str
    classes: list[ClassTargetOut]


def _target_allocation(ctx: ToolContext, args: TargetAllocationInput) -> TargetAllocationOut:
    target = target_allocation(args.risk, args.horizon)
    return TargetAllocationOut(
        risk=args.risk,
        horizon=args.horizon,
        classes=[
            ClassTargetOut(asset_class=cls, target_pct=f"{pct:.1f}") for cls, pct in target.items()
        ],
    )


TARGET_ALLOCATION = Tool(
    name="target_allocation",
    description=(
        "Zwraca docelowy podział portfela na klasy aktywów (udział w %, suma 100) "
        "dla tolerancji ryzyka (low, medium, high) i horyzontu (short, medium, long)."
    ),
    input_model=TargetAllocationInput,
    func=_target_allocation,
    group="calc",
)


# --- E5-05: purchase simulation, growth, goals, budget proposal ---------------------------------

AssetClass = Literal["stock", "etf", "bond", "real_estate", "commodity", "crypto", "cash"]
Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
Rate = Annotated[Decimal, Field(ge=0, le=30, max_digits=6, decimal_places=2)]


class SimulatePurchaseInput(BaseModel):
    asset_class: AssetClass
    amount: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


class ShareOut(BaseModel):
    asset_class: str
    value: str
    share_pct: str


class SimulatePurchaseOut(BaseModel):
    asset_class: str
    amount: str
    total_before: str
    total_after: str
    new_class: bool
    before: list[ShareOut]
    after: list[ShareOut]


class CompoundInterestInput(BaseModel):
    principal: Money
    monthly: Money
    annual_rate_pct: Rate
    years: Annotated[int, Field(ge=1, le=50)]


class YearOut(BaseModel):
    year: int
    balance: str
    contributed: str


class CompoundInterestOut(BaseModel):
    final_value: str
    contributed: str
    interest: str
    yearly: list[YearOut]


class SavingsGoalInput(BaseModel):
    target: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    current: Money = Decimal(0)
    months: Annotated[int, Field(ge=1, le=600)]
    annual_rate_pct: Rate = Decimal(0)


class SavingsGoalOut(BaseModel):
    monthly_amount: str
    months: int
    target: str
    current: str
    annual_rate_pct: str


class ProposeBudgetInput(BaseModel):
    month: MonthStr
    months_back: Annotated[int, Field(ge=1, le=6)] = 3
    cut_pct: Annotated[Decimal, Field(ge=0, le=50, max_digits=5, decimal_places=2)] = Decimal(10)


class ProposedLimitOut(BaseModel):
    category: str
    average: str
    proposed_limit: str
    current_limit: str | None


class ProposeBudgetOut(BaseModel):
    from_month: str
    to_month: str
    months_back: int
    cut_pct: str
    average_income: str
    average_expenses: str
    average_surplus: str
    proposed_limits: list[ProposedLimitOut]


def _shares(items: list) -> list[ShareOut]:
    return [
        ShareOut(asset_class=i.asset_class, value=f"{i.value:.2f}", share_pct=f"{i.share_pct:.1f}")
        for i in items
    ]


def _simulate_purchase(ctx: ToolContext, args: SimulatePurchaseInput) -> SimulatePurchaseOut:
    result = portfolio_service.summary(ctx.db, ctx.user_id)
    classes = [ClassValue(a.asset_class, a.value) for a in result.summary.allocation]
    impact = simulate_purchase(classes, args.asset_class, args.amount)
    return SimulatePurchaseOut(
        asset_class=args.asset_class,
        amount=f"{args.amount:.2f}",
        total_before=f"{impact.total_before:.2f}",
        total_after=f"{impact.total_after:.2f}",
        new_class=impact.new_class,
        before=_shares(impact.before),
        after=_shares(impact.after),
    )


def _compound_interest(ctx: ToolContext, args: CompoundInterestInput) -> CompoundInterestOut:
    r = compound_growth(args.principal, args.monthly, args.annual_rate_pct, args.years)
    return CompoundInterestOut(
        final_value=f"{r.final_value:.2f}",
        contributed=f"{r.contributed:.2f}",
        interest=f"{r.interest:.2f}",
        yearly=[
            YearOut(year=y.year, balance=f"{y.balance:.2f}", contributed=f"{y.contributed:.2f}")
            for y in r.yearly
        ],
    )


def _savings_goal_plan(ctx: ToolContext, args: SavingsGoalInput) -> SavingsGoalOut:
    amount = monthly_saving_for_goal(args.target, args.current, args.months, args.annual_rate_pct)
    return SavingsGoalOut(
        monthly_amount=f"{amount:.2f}",
        months=args.months,
        target=f"{args.target:.2f}",
        current=f"{args.current:.2f}",
        annual_rate_pct=f"{args.annual_rate_pct:.2f}",
    )


def _propose_budget(ctx: ToolContext, args: ProposeBudgetInput) -> ProposeBudgetOut:
    summaries = budget_service.month_summaries(ctx.db, ctx.user_id, args.month, args.months_back)
    averages = average_by_category(summaries)
    growth = (
        {g.category_id for g in top_growth(summaries[0], summaries[1:], n=len(averages) or 1)}
        if len(summaries) > 1
        else set()
    )
    proposed = propose_limits(averages, growth, args.cut_pct)
    limits = {v.category_id: v.amount for v in budget_service.list_limits(ctx.db, ctx.user_id)}
    income, expenses, surplus = average_totals(summaries)
    return ProposeBudgetOut(
        from_month=summaries[-1].month,
        to_month=summaries[0].month,
        months_back=args.months_back,
        cut_pct=f"{args.cut_pct:.1f}",
        average_income=f"{income:.2f}",
        average_expenses=f"{expenses:.2f}",
        average_surplus=f"{surplus:.2f}",
        proposed_limits=[
            ProposedLimitOut(
                category=p.category_name,
                average=f"{p.average:.2f}",
                proposed_limit=f"{p.proposed:.2f}",
                current_limit=None
                if p.category_id not in limits
                else f"{limits[p.category_id]:.2f}",
            )
            for p in proposed
        ],
    )


SIMULATE_PURCHASE = Tool(
    name="simulate_purchase",
    description=(
        "Symuluje zakup aktywów za podaną kwotę w PLN na portfelu użytkownika: zwraca podział "
        "na klasy aktywów (wartość i udział %) przed i po zakupie oraz informację, czy klasa "
        "jest nowa w portfelu. Klasy: stock, etf, bond, real_estate, commodity, crypto, cash."
    ),
    input_model=SimulatePurchaseInput,
    func=_simulate_purchase,
    group="calc",
)

COMPOUND_INTEREST = Tool(
    name="compound_interest",
    description=(
        "Liczy wartość oszczędności z kapitalizacją miesięczną: kapitał początkowy, wpłata "
        "miesięczna, roczna stopa w % (0-30), horyzont w latach (1-50). Zwraca wartość końcową, "
        "sumę wpłat, odsetki i stan na koniec każdego roku. To przykład, a nie prognoza."
    ),
    input_model=CompoundInterestInput,
    func=_compound_interest,
    group="calc",
)

SAVINGS_GOAL_PLAN = Tool(
    name="savings_goal_plan",
    description=(
        "Liczy miesięczną kwotę potrzebną do zebrania celu oszczędnościowego: kwota celu, "
        "obecne oszczędności, liczba miesięcy i opcjonalna roczna stopa w % (0-30)."
    ),
    input_model=SavingsGoalInput,
    func=_savings_goal_plan,
    group="calc",
)

PROPOSE_BUDGET = Tool(
    name="propose_budget",
    description=(
        "Proponuje limity budżetowe na podstawie średnich wydatków z ostatnich miesięcy "
        "(do 6, kończąc na wskazanym miesiącu RRRR-MM): średnia per kategoria, dla kategorii "
        "o rosnących wydatkach pomniejszona o cut_pct (0-50%), zaokrąglona w górę do 10 zł; "
        "zwraca też obecny limit oraz średnie przychody, wydatki i nadwyżkę."
    ),
    input_model=ProposeBudgetInput,
    func=_propose_budget,
    group="calc",
)
