"""budget_plan: proposed monthly limits from average spending and a savings goal (F13, F17, F31)."""

from decimal import Decimal
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from coffer.agent.actions.base import Action, ActionContext, Prepared
from coffer.agent.actions.savings_analysis import BUDGET_DISCLAIMER
from coffer.agent.schemas import (
    Fact,
    Finding,
    ParamSpec,
    Recommendation,
    ReportDraft,
    Table,
    TableColumn,
)
from coffer.analytics.planning import previous_month
from coffer.transactions.service import list_categories

NO_RECENT_TRANSACTIONS = "Brak transakcji w ostatnich miesiącach."
CUT_PCT = Decimal(10)
EXAMPLE_RATE = Decimal(3)
EXAMPLE_YEARS = 5


class BudgetPlanParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    months_back: Annotated[int, Field(ge=1, le=6)] = 3
    savings_target: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)] | None = None
    target_months: Annotated[int, Field(ge=1, le=120)] | None = None

    @model_validator(mode="after")
    def _goal_is_complete(self) -> Self:
        if (self.savings_target is None) != (self.target_months is None):
            raise ValueError("Podaj jednocześnie kwotę celu i liczbę miesięcy.")
        return self


def prepare(ctx: ActionContext, params: BudgetPlanParams) -> Prepared:
    month = previous_month(ctx.now.date())
    plan = ctx.call(
        "propose_budget",
        {"month": month, "months_back": params.months_back, "cut_pct": str(CUT_PCT)},
    )
    income, expenses, surplus = (
        Decimal(plan["average_income"]),
        Decimal(plan["average_expenses"]),
        Decimal(plan["average_surplus"]),
    )
    if income == 0 and expenses == 0:
        return Prepared(no_data=NO_RECENT_TRANSACTIONS)

    facts = [
        Fact(label="Średnie przychody", value=plan["average_income"], kind="money"),
        Fact(label="Średnie wydatki", value=plan["average_expenses"], kind="money"),
        Fact(label="Średnia nadwyżka", value=plan["average_surplus"], kind="money"),
    ]
    goal: dict[str, Any] | None = None
    if params.savings_target is not None and params.target_months is not None:
        goal = ctx.call(
            "savings_goal_plan",
            {
                "target": str(params.savings_target),
                "current": "0",
                "months": params.target_months,
                "annual_rate_pct": "0",
            },
        )
        facts.append(
            Fact(label="Wymagana kwota miesięczna", value=goal["monthly_amount"], kind="money")
        )
    example: dict[str, Any] | None = None
    if surplus > 0:
        example = ctx.call(
            "compound_interest",
            {
                "principal": "0",
                "monthly": plan["average_surplus"],
                "annual_rate_pct": str(EXAMPLE_RATE),
                "years": EXAMPLE_YEARS,
            },
        )
        facts.append(
            Fact(
                label=f"Przykład: nadwyżka odkładana {EXAMPLE_YEARS} lat przy {EXAMPLE_RATE}%/rok",
                value=example["final_value"],
                kind="money",
            )
        )
    rows = [
        {
            "category": p["category"],
            "average": p["average"],
            "proposed_limit": p["proposed_limit"],
            "current_limit": p["current_limit"] or "—",
        }
        for p in plan["proposed_limits"]
    ]
    # Table rows carry `category_id` for the frontend (no column); the model never sees it.
    ids = {c.name: str(c.id) for c in list_categories(ctx.db)}
    table_rows = [{**r, "category_id": ids.get(r["category"], "")} for r in rows]
    table = Table(
        id="proposed_limits",
        title="Proponowane limity miesięczne",
        columns=[
            TableColumn(key="category", label="Kategoria", kind="text"),
            TableColumn(key="average", label="Średnia", kind="money"),
            TableColumn(key="proposed_limit", label="Proponowany limit", kind="money"),
            TableColumn(key="current_limit", label="Obecny limit", kind="money"),
        ],
        rows=table_rows,
    )
    snapshot: dict[str, Any] = {
        "from_month": plan["from_month"],
        "to_month": plan["to_month"],
        "months_back": params.months_back,
        "average_income": plan["average_income"],
        "average_expenses": plan["average_expenses"],
        "average_surplus": plan["average_surplus"],
        "cut_pct": plan["cut_pct"],
        "goal_monthly": None if goal is None else goal["monthly_amount"],
        "goal_target": None if params.savings_target is None else str(params.savings_target),
        "goal_months": params.target_months,
        "example_final": None if example is None else example["final_value"],
        "limits": rows,
    }
    context: dict[str, Any] = {
        "okres": f"{plan['from_month']} do {plan['to_month']}",
        "fakty": {f.label: f.value for f in facts},
        "proponowane_limity": rows[:12],
        "obnizka_dla_rosnacych_kategorii_pct": plan["cut_pct"],
        "przyklad": (
            None
            if example is None
            else f"{EXAMPLE_YEARS} lat, {EXAMPLE_RATE}% rocznie (przykład, nie prognoza): "
            f"wpłaty {example['contributed']}, odsetki {example['interest']}"
        ),
    }
    return Prepared(facts=facts, tables=[table], context=context, snapshot=snapshot)


def fallback(prepared: Prepared, params: BudgetPlanParams) -> ReportDraft:
    snap = prepared.snapshot
    findings = [
        Finding(
            title="Średni budżet miesięczny",
            detail=f"W okresie {snap['from_month']} do {snap['to_month']} średnie przychody to "
            f"{snap['average_income']} PLN, wydatki {snap['average_expenses']} PLN, nadwyżka "
            f"{snap['average_surplus']} PLN.",
            refers_to="budget",
            value=snap["average_surplus"],
        )
    ]
    recommendations = [
        Recommendation(
            title=f"Ustaw limit: {r['category']}",
            detail=f"Średnie wydatki {r['average']} PLN, proponowany limit "
            f"{r['proposed_limit']} PLN (obecny: {r['current_limit']}).",
            amount=r["proposed_limit"],
        )
        for r in snap["limits"][:4]
    ]
    risks = [
        "Limity wynikają ze średnich z kilku miesięcy i nie uwzględniają wydatków jednorazowych."
    ]
    if snap["goal_monthly"] is not None:
        need, surplus = Decimal(snap["goal_monthly"]), Decimal(snap["average_surplus"])
        reachable = need <= surplus
        findings.append(
            Finding(
                title="Cel oszczędnościowy",
                detail=f"Aby zebrać {snap['goal_target']} PLN w {snap['goal_months']} mies., "
                f"trzeba odkładać {snap['goal_monthly']} PLN miesięcznie; średnia nadwyżka to "
                f"{snap['average_surplus']} PLN, więc cel jest "
                + (
                    "osiągalny."
                    if reachable
                    else "trudny do osiągnięcia bez ograniczenia wydatków."
                ),
                refers_to="calc",
                value=snap["goal_monthly"],
            )
        )
        if not reachable:
            recommendations.append(
                Recommendation(
                    title="Wydłuż termin albo zmniejsz cel",
                    detail=f"Wymagane {snap['goal_monthly']} PLN/mies. przekracza średnią nadwyżkę "
                    f"{snap['average_surplus']} PLN.",
                    amount=snap["goal_monthly"],
                )
            )
    if snap["example_final"] is not None:
        findings.append(
            Finding(
                title="Przykład oszczędzania nadwyżki",
                detail=f"Odkładanie średniej nadwyżki przez {EXAMPLE_YEARS} lat przy "
                f"{EXAMPLE_RATE}% rocznie dałoby {snap['example_final']} PLN. To przykład "
                "obliczeniowy, a nie prognoza.",
                refers_to="calc",
                value=snap["example_final"],
            )
        )
    return ReportDraft(
        headline=f"Plan budżetu: średnia nadwyżka {snap['average_surplus']} PLN miesięcznie.",
        findings=findings[:6],
        recommendations=recommendations[:5],
        risks=risks,
    )


BUDGET_PLAN = Action(
    id="budget_plan",
    name="Plan budżetu",
    description="Proponuje limity wydatków na podstawie średnich z ostatnich miesięcy i, "
    "opcjonalnie, liczy miesięczną kwotę potrzebną na cel oszczędnościowy.",
    params_model=BudgetPlanParams,
    params_ui=(
        ParamSpec(
            name="months_back",
            label="Średnia z ostatnich miesięcy",
            kind="int",
            default=3,
            help="Od 1 do 6 pełnych miesięcy.",
        ),
        ParamSpec(name="savings_target", label="Cel oszczędnościowy (PLN)", kind="amount"),
        ParamSpec(
            name="target_months",
            label="Termin celu (miesiące)",
            kind="int",
            help="Od 1 do 120; podaj razem z kwotą celu.",
        ),
    ),
    prompt_version="budget_plan_v1",
    tools=(
        "get_months_overview",
        "get_category_limits",
        "propose_budget",
        "savings_goal_plan",
        "compound_interest",
    ),
    draft_model=ReportDraft,
    disclaimer=BUDGET_DISCLAIMER,
    uses_user_data=True,
    uses_internet=False,
    prepare=prepare,
    fallback=fallback,
)
