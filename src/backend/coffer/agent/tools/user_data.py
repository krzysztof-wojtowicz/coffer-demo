from pydantic import BaseModel

from coffer.agent.tools.registry import Tool, ToolContext
from coffer.analytics.shares import category_shares
from coffer.budget import service as budget_service
from coffer.core.months import MonthStr
from coffer.profile import service as profile_service

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
)

GET_INVESTMENT_PROFILE = Tool(
    name="get_investment_profile",
    description=(
        "Zwraca profil inwestycyjny użytkownika: horyzont, tolerancję ryzyka i preferowane "
        "klasy aktywów. Pole available=false oznacza brak profilu."
    ),
    input_model=EmptyInput,
    func=get_investment_profile,
)
