"""savings_analysis: where the user can save, from month comparison, growth and limits (F12-F15)."""

from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from coffer.agent.actions.base import Action, ActionContext, Prepared
from coffer.agent.schemas import (
    Fact,
    Finding,
    ParamSpec,
    Recommendation,
    ReportDraft,
    Table,
    TableColumn,
)
from coffer.analytics.spending import cut_savings
from coffer.core.months import MonthStr

NO_TRANSACTIONS = "Brak transakcji w wybranym miesiącu."
CUT_PCT = Decimal(10)
BUDGET_DISCLAIMER = (
    "To są wyliczenia informacyjne oparte na Twoich danych, a nie porada finansowa. "
    "Decyzje o wydatkach podejmujesz samodzielnie."
)


class SavingsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    month: MonthStr | None = None
    months_back: Annotated[int, Field(ge=1, le=6)] = 3


def _cols(*items: tuple[str, str, Any]) -> list[TableColumn]:
    return [TableColumn(key=k, label=label, kind=kind) for k, label, kind in items]


def _pct(value: str | None) -> str:
    return "—" if value is None else value


def prepare(ctx: ActionContext, params: SavingsParams) -> Prepared:
    month = params.month or ctx.now.strftime("%Y-%m")
    analysis = ctx.call("get_month_analysis", {"month": month})
    if Decimal(analysis["income"]) == 0 and Decimal(analysis["expenses"]) == 0:
        return Prepared(no_data=NO_TRANSACTIONS)
    insights = ctx.call("get_spending_insights", {"month": month})
    stats = ctx.call("get_transaction_stats", {"month": month, "months": params.months_back})

    totals = insights["totals"]
    exceeded = [x for x in insights["limits"] if x["exceeded"]]
    growth = []
    for g in insights["top_growth"]:
        monthly, yearly = cut_savings(Decimal(g["current"]), CUT_PCT)
        growth.append({**g, "cut_monthly": f"{monthly:.2f}", "cut_yearly": f"{yearly:.2f}"})

    facts = [
        Fact(label="Wydatki", value=analysis["expenses"], kind="money"),
        Fact(label="Nadwyżka", value=analysis["surplus"], kind="money"),
        Fact(label="Zmiana wydatków vs poprzedni miesiąc", value=totals["change"], kind="money"),
        Fact(label="Liczba przekroczonych limitów", value=str(len(exceeded)), kind="number"),
    ]
    if totals["change_pct"] is not None:
        facts.insert(
            3, Fact(label="Zmiana wydatków (%)", value=totals["change_pct"], kind="percent")
        )
    tables = [
        Table(
            id="comparison",
            title=f"Wydatki: {insights['month']} vs {insights['previous_month']}",
            columns=_cols(
                ("category", "Kategoria", "text"),
                ("current", "Bieżący miesiąc", "money"),
                ("previous", "Poprzedni miesiąc", "money"),
                ("change", "Zmiana", "money"),
                ("change_pct", "Zmiana (%)", "percent"),
            ),
            rows=[
                {
                    **{k: c[k] for k in ("category", "current", "previous", "change")},
                    "change_pct": _pct(c["change_pct"]),
                }
                for c in insights["comparison"]
            ],
        ),
        Table(
            id="top_growth",
            title="Największy wzrost wydatków względem średniej z 3 poprzednich miesięcy",
            columns=_cols(
                ("category", "Kategoria", "text"),
                ("current", "Bieżący miesiąc", "money"),
                ("average_3m", "Średnia (3 mies.)", "money"),
                ("increase", "Wzrost", "money"),
                ("increase_pct", "Wzrost (%)", "percent"),
            ),
            rows=[
                {
                    **{k: g[k] for k in ("category", "current", "average_3m", "increase")},
                    "increase_pct": _pct(g["increase_pct"]),
                }
                for g in growth
            ],
        ),
        Table(
            id="limits",
            title="Limity budżetowe",
            columns=_cols(
                ("category", "Kategoria", "text"),
                ("limit", "Limit", "money"),
                ("spent", "Wydano", "money"),
                ("remaining", "Pozostało", "money"),
                ("used_pct", "Wykorzystanie (%)", "percent"),
                ("status", "Status", "text"),
            ),
            rows=[
                {
                    **{k: x[k] for k in ("category", "limit", "spent", "remaining", "used_pct")},
                    "status": "przekroczony" if x["exceeded"] else "w normie",
                }
                for x in insights["limits"]
            ],
        ),
    ]
    snapshot: dict[str, Any] = {
        "month": month,
        "months_back": params.months_back,
        "expenses": analysis["expenses"],
        "surplus": analysis["surplus"],
        "totals": totals,
        "exceeded": exceeded,
        "top_growth": growth,
        "cut_pct": str(CUT_PCT),
    }
    context: dict[str, Any] = {
        "miesiac": month,
        "fakty": {f.label: f.value for f in facts},
        "porownanie_kategorii": tables[0].rows[:8],
        "najwiekszy_wzrost": growth,
        "limity": tables[2].rows,
        "statystyki_kategorii": stats["categories"][:8],
        "uwaga": f"cut_pct={CUT_PCT}: przykładowe ograniczenie wydatków o {CUT_PCT}%",
    }
    return Prepared(facts=facts, tables=tables, context=context, snapshot=snapshot)


def fallback(prepared: Prepared, params: SavingsParams) -> ReportDraft:
    snap = prepared.snapshot
    totals = snap["totals"]
    change = Decimal(totals["change"])
    trend = "wzrosły" if change > 0 else "spadły" if change < 0 else "nie zmieniły się"
    findings = [
        Finding(
            title="Wydatki w miesiącu",
            detail=f"Wydatki w {snap['month']} to {snap['expenses']} PLN, nadwyżka "
            f"{snap['surplus']} PLN. W porównaniu z poprzednim miesiącem {trend} "
            f"(zmiana {totals['change']} PLN).",
            refers_to="budget",
            value=snap["expenses"],
        )
    ]
    recommendations: list[Recommendation] = []
    for x in snap["exceeded"][:3]:
        over = Decimal(x["spent"]) - Decimal(x["limit"])
        findings.append(
            Finding(
                title=f"Przekroczony limit: {x['category']}",
                detail=f"Wydano {x['spent']} PLN przy limicie {x['limit']} PLN "
                f"(o {over:.2f} PLN więcej).",
                refers_to="budget",
                value=f"{over:.2f}",
            )
        )
        recommendations.append(
            Recommendation(
                title=f"Zmniejsz wydatki: {x['category']}",
                detail=f"Limit {x['limit']} PLN został przekroczony o {over:.2f} PLN.",
                amount=f"{over:.2f}",
            )
        )
    for g in snap["top_growth"]:
        if len(recommendations) >= 5:
            break
        recommendations.append(
            Recommendation(
                title=f"Ogranicz wydatki: {g['category']}",
                detail=f"Wydatki wzrosły o {g['increase']} PLN względem średniej. "
                f"Ograniczenie o {snap['cut_pct']}% = {g['cut_monthly']} zł/mies., "
                f"{g['cut_yearly']} zł/rok.",
                amount=g["cut_monthly"],
            )
        )
    if not snap["exceeded"] and not snap["top_growth"]:
        findings.append(
            Finding(
                title="Brak wyraźnych obszarów do oszczędzania",
                detail="Żaden limit nie jest przekroczony i żadna kategoria nie rośnie "
                "względem średniej.",
                refers_to="budget",
            )
        )
    risks = ["Wnioski opierają się na danych z kilku miesięcy i mogą pomijać wydatki sezonowe."]
    return ReportDraft(
        headline=f"Wydatki w {snap['month']}: {snap['expenses']} PLN, "
        f"przekroczone limity: {len(snap['exceeded'])}.",
        findings=findings[:6],
        recommendations=recommendations[:5],
        risks=risks,
    )


SAVINGS_ANALYSIS = Action(
    id="savings_analysis",
    name="Gdzie zaoszczędzić",
    description="Porównuje wydatki z poprzednim miesiącem, wskazuje kategorie o największym "
    "wzroście i przekroczone limity oraz pokazuje, ile da się zaoszczędzić.",
    params_model=SavingsParams,
    params_ui=(
        ParamSpec(name="month", label="Miesiąc", kind="month", help="Domyślnie bieżący miesiąc."),
        ParamSpec(
            name="months_back",
            label="Historia (miesiące)",
            kind="int",
            default=3,
            help="Od 1 do 6 miesięcy do statystyk kategorii.",
        ),
    ),
    prompt_version="savings_analysis_v1",
    tools=(
        "get_month_analysis",
        "get_spending_insights",
        "get_transaction_stats",
        "get_category_limits",
        "get_months_overview",
    ),
    draft_model=ReportDraft,
    disclaimer=BUDGET_DISCLAIMER,
    uses_user_data=True,
    uses_internet=False,
    prepare=prepare,
    fallback=fallback,
)
