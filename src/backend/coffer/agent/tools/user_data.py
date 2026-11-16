from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from coffer.agent.tools.registry import Tool, ToolContext
from coffer.analytics.limits import LimitStatus, limit_status
from coffer.analytics.net_worth import portfolio_is_complete
from coffer.analytics.planning import shift_month
from coffer.analytics.shares import category_shares
from coffer.analytics.spending import category_stats, total_change
from coffer.budget import service as budget_service
from coffer.core.months import MonthStr, parse_month
from coffer.market import service as market_service
from coffer.portfolio import service as portfolio_service
from coffer.profile import service as profile_service
from coffer.transactions.service import list_views

HORIZON_LABELS = {
    "short": "krótki (do 2 lat)",
    "medium": "średni (2–5 lat)",
    "long": "długi (powyżej 5 lat)",
}
RISK_LABELS = {"low": "niska", "medium": "średnia", "high": "wysoka"}
CLASS_LABELS = {
    "cash": "gotówka",
    "deposit": "lokaty",
    "stocks": "akcje",
    "etf": "fundusze ETF",
    "bonds": "obligacje",
    "crypto": "kryptowaluty",
    "real_estate": "nieruchomości",
}


class MonthInput(BaseModel):
    month: MonthStr


class CategoryOut(BaseModel):
    category: str
    expenses: str
    share_pct: str


class MonthAnalysisOut(BaseModel):
    month: str
    income: str
    expenses: str
    balance: str
    surplus: str
    by_category: list[CategoryOut]


class EmptyInput(BaseModel):
    pass


class InvestmentProfileOut(BaseModel):
    available: bool
    horizon: str | None = None
    horizon_label: str | None = None
    risk: str | None = None
    risk_label: str | None = None
    preferred_classes: list[str] = []
    preferred_classes_labels: list[str] = []


class ClassValueOut(BaseModel):
    asset_class: str
    value: str  # PLN
    share_pct: str


class PositionOut(BaseModel):
    symbol: str | None
    asset_class: str
    value: str  # PLN
    share_pct: str | None
    gain_pct: str | None
    priced: bool  # valued from a market quote (not a manual value or cost)


class PortfolioOut(BaseModel):
    total_value: str  # PLN
    complete: bool
    classes: list[ClassValueOut]
    positions: list[PositionOut]


class NetWorthOut(BaseModel):
    cash_balance: str
    portfolio_value: str
    net_worth: str
    portfolio_complete: bool


def get_month_analysis(ctx: ToolContext, args: MonthInput) -> MonthAnalysisOut:
    s = budget_service.month_summary(ctx.db, ctx.user_id, args.month)
    shares = category_shares(s.by_category, s.expenses)
    return MonthAnalysisOut(
        month=s.month,
        income=f"{s.income:.2f}",
        expenses=f"{s.expenses:.2f}",
        balance=f"{s.balance:.2f}",
        surplus=f"{s.surplus:.2f}",
        by_category=[
            CategoryOut(
                category=c.category_name, expenses=f"{c.expenses:.2f}", share_pct=f"{p:.1f}"
            )
            for c, p in zip(s.by_category, shares, strict=True)
        ],
    )


def get_investment_profile(ctx: ToolContext, args: EmptyInput) -> InvestmentProfileOut:
    p = profile_service.get(ctx.db, ctx.user_id)
    if p is None:
        return InvestmentProfileOut(available=False)
    classes = list(p.preferred_classes)
    return InvestmentProfileOut(
        available=True,
        horizon=p.horizon,
        horizon_label=HORIZON_LABELS.get(p.horizon, p.horizon),
        risk=p.risk,
        risk_label=RISK_LABELS.get(p.risk, p.risk),
        preferred_classes=classes,
        preferred_classes_labels=[CLASS_LABELS.get(c, c) for c in classes],
    )


def _safe_symbol(symbol: str | None) -> str | None:
    return market_service.normalize_symbol(symbol or "")


def get_portfolio(ctx: ToolContext, args: EmptyInput) -> PortfolioOut:
    """Aggregates only: no names, notes or ids (N03). Holdings without a PLN rate are left out
    of positions and make the portfolio incomplete."""
    result = portfolio_service.summary(ctx.db, ctx.user_id)
    s = result.summary
    return PortfolioOut(
        total_value=f"{s.total_value:.2f}",
        complete=portfolio_is_complete(s, result.prices_available),
        classes=[
            ClassValueOut(
                asset_class=a.asset_class, value=f"{a.value:.2f}", share_pct=f"{a.share_pct:.1f}"
            )
            for a in s.allocation
        ],
        positions=[
            PositionOut(
                symbol=_safe_symbol(h.symbol),
                asset_class=h.asset_class,
                value=f"{h.current_value:.2f}",
                share_pct=None if h.share_pct is None else f"{h.share_pct:.1f}",
                gain_pct=None if h.gain_pct is None else f"{h.gain_pct:.1f}",
                priced=h.value_source == "market",
            )
            for h in s.holdings
            if h.converted
        ],
    )


def get_net_worth(ctx: ToolContext, args: EmptyInput) -> NetWorthOut:
    nw = budget_service.net_worth(ctx.db, ctx.user_id, ctx.now.date())
    return NetWorthOut(
        cash_balance=f"{nw.cash_balance:.2f}",
        portfolio_value=f"{nw.portfolio_value:.2f}",
        net_worth=f"{nw.net_worth:.2f}",
        portfolio_complete=nw.portfolio_complete,
    )


GET_MONTH_ANALYSIS = Tool(
    name="get_month_analysis",
    description=(
        "Zwraca analizę budżetu użytkownika za wskazany miesiąc (RRRR-MM): przychody, "
        "wydatki, bilans (ze wszystkich transakcji, także inwestycji i przelewów własnych), "
        "nadwyżkę (tylko z kategorii budżetowych) oraz wydatki i udział procentowy "
        "w podziale na kategorie."
    ),
    input_model=MonthInput,
    func=get_month_analysis,
    group="user_data",
)

GET_INVESTMENT_PROFILE = Tool(
    name="get_investment_profile",
    description=(
        "Zwraca profil inwestycyjny użytkownika: horyzont, tolerancję ryzyka i preferowane "
        "klasy aktywów. Pole available=false oznacza brak profilu."
    ),
    input_model=EmptyInput,
    func=get_investment_profile,
    group="user_data",
)

GET_PORTFOLIO = Tool(
    name="get_portfolio",
    description=(
        "Zwraca wycenę portfela użytkownika w PLN: wartość łączną, wartość i udział % klas "
        "aktywów oraz pozycje (symbol, klasa, wartość, udział %, zysk %, czy wycena z notowania). "
        "Pole complete=false oznacza niepełną wycenę (brak notowań lub kursów)."
    ),
    input_model=EmptyInput,
    func=get_portfolio,
    group="user_data",
)

GET_NET_WORTH = Tool(
    name="get_net_worth",
    description=(
        "Zwraca majątek netto użytkownika w PLN: saldo gotówki, wartość portfela i ich sumę. "
        "Pole portfolio_complete=false oznacza niepełną wycenę portfela."
    ),
    input_model=EmptyInput,
    func=get_net_worth,
    group="user_data",
)


# --- budget tools (E5-05): aggregates per month and category, never descriptions -----------------


class MonthsOverviewInput(BaseModel):
    month: MonthStr
    count: Annotated[int, Field(ge=1, le=12)] = 3


class MonthRowOut(BaseModel):
    month: str
    income: str
    expenses: str
    balance: str
    surplus: str


class MonthsOverviewOut(BaseModel):
    months: list[MonthRowOut]  # newest first


class ChangeOut(BaseModel):
    category: str
    current: str
    previous: str
    change: str
    change_pct: str | None


class GrowthOut(BaseModel):
    category: str
    current: str
    average_3m: str
    increase: str
    increase_pct: str | None


class LimitOut(BaseModel):
    category: str
    limit: str
    spent: str
    remaining: str
    used_pct: str
    exceeded: bool


class TotalsOut(BaseModel):
    current: str
    previous: str
    change: str
    change_pct: str | None


class SpendingInsightsOut(BaseModel):
    month: str
    previous_month: str
    totals: TotalsOut
    comparison: list[ChangeOut]
    top_growth: list[GrowthOut]
    limits: list[LimitOut]


class TransactionStatsInput(BaseModel):
    month: MonthStr
    months: Annotated[int, Field(ge=1, le=6)] = 3


class CategoryStatOut(BaseModel):
    category: str
    count: int
    total: str
    average: str
    largest: str


class TransactionStatsOut(BaseModel):
    from_month: str
    to_month: str
    categories: list[CategoryStatOut]


class CategoryLimitsOut(BaseModel):
    month: str
    limits: list[LimitOut]


def _opt(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.1f}"


def _limit_out(s: LimitStatus) -> LimitOut:
    return LimitOut(
        category=s.category_name,
        limit=f"{s.limit:.2f}",
        spent=f"{s.spent:.2f}",
        remaining=f"{s.remaining:.2f}",
        used_pct=f"{s.used_pct:.1f}",
        exceeded=s.exceeded,
    )


def get_months_overview(ctx: ToolContext, args: MonthsOverviewInput) -> MonthsOverviewOut:
    rows = budget_service.month_summaries(ctx.db, ctx.user_id, args.month, args.count)
    return MonthsOverviewOut(
        months=[
            MonthRowOut(
                month=s.month,
                income=f"{s.income:.2f}",
                expenses=f"{s.expenses:.2f}",
                balance=f"{s.balance:.2f}",
                surplus=f"{s.surplus:.2f}",
            )
            for s in rows
        ]
    )


def get_spending_insights(ctx: ToolContext, args: MonthInput) -> SpendingInsightsOut:
    ins = budget_service.month_insights(ctx.db, ctx.user_id, args.month)
    totals = total_change(ins.comparison)
    return SpendingInsightsOut(
        month=ins.month,
        previous_month=ins.previous_month,
        totals=TotalsOut(
            current=f"{totals.current:.2f}",
            previous=f"{totals.previous:.2f}",
            change=f"{totals.change:.2f}",
            change_pct=_opt(totals.change_pct),
        ),
        comparison=[
            ChangeOut(
                category=c.category_name,
                current=f"{c.current:.2f}",
                previous=f"{c.previous:.2f}",
                change=f"{c.change:.2f}",
                change_pct=_opt(c.change_pct),
            )
            for c in ins.comparison
        ],
        top_growth=[
            GrowthOut(
                category=g.category_name,
                current=f"{g.current:.2f}",
                average_3m=f"{g.average_3m:.2f}",
                increase=f"{g.increase:.2f}",
                increase_pct=_opt(g.increase_pct),
            )
            for g in ins.top_growth
        ],
        limits=[_limit_out(s) for s in ins.limits],
    )


def get_transaction_stats(ctx: ToolContext, args: TransactionStatsInput) -> TransactionStatsOut:
    """Expense counts and totals per category over the last `months` months (no descriptions)."""
    first = shift_month(args.month, -(args.months - 1))
    start, _ = parse_month(first)
    _, end = parse_month(args.month)
    stats = category_stats(list_views(ctx.db, ctx.user_id, start, end))
    return TransactionStatsOut(
        from_month=first,
        to_month=args.month,
        categories=[
            CategoryStatOut(
                category=s.category_name,
                count=s.count,
                total=f"{s.total:.2f}",
                average=f"{s.average:.2f}",
                largest=f"{s.largest:.2f}",
            )
            for s in stats
        ],
    )


def get_category_limits(ctx: ToolContext, args: MonthInput) -> CategoryLimitsOut:
    summary = budget_service.month_summary(ctx.db, ctx.user_id, args.month)
    limits = {
        v.category_id: (v.category_name, v.amount)
        for v in budget_service.list_limits(ctx.db, ctx.user_id)
    }
    return CategoryLimitsOut(
        month=args.month,
        limits=[_limit_out(s) for s in limit_status(summary.by_category, limits)],
    )


GET_MONTHS_OVERVIEW = Tool(
    name="get_months_overview",
    description=(
        "Zwraca przychody, wydatki, bilans i nadwyżkę za kilka kolejnych miesięcy "
        "(od wskazanego miesiąca RRRR-MM wstecz, od 1 do 12 miesięcy, najnowszy pierwszy)."
    ),
    input_model=MonthsOverviewInput,
    func=get_months_overview,
    group="user_data",
)

GET_SPENDING_INSIGHTS = Tool(
    name="get_spending_insights",
    description=(
        "Zwraca wnioski o wydatkach za miesiąc (RRRR-MM): sumę wydatków i jej zmianę względem "
        "poprzedniego miesiąca, porównanie kategorii, trzy kategorie o największym wzroście "
        "względem średniej z trzech poprzednich miesięcy oraz stan limitów budżetowych."
    ),
    input_model=MonthInput,
    func=get_spending_insights,
    group="user_data",
)

GET_TRANSACTION_STATS = Tool(
    name="get_transaction_stats",
    description=(
        "Zwraca statystyki wydatków per kategoria (liczba transakcji, suma, średnia, największy "
        "wydatek) za ostatnie miesiące (1-6) kończące się na wskazanym miesiącu RRRR-MM. "
        "Bez opisów transakcji."
    ),
    input_model=TransactionStatsInput,
    func=get_transaction_stats,
    group="user_data",
)

GET_CATEGORY_LIMITS = Tool(
    name="get_category_limits",
    description=(
        "Zwraca limity budżetowe użytkownika i ich wykorzystanie w miesiącu (RRRR-MM): limit, "
        "wydano, pozostało, wykorzystanie w % i informację o przekroczeniu."
    ),
    input_model=MonthInput,
    func=get_category_limits,
    group="user_data",
)
