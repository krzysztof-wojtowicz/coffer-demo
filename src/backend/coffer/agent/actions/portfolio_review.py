"""portfolio_review: allocation vs. a target for the user's risk profile (F23, F32, F36)."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from coffer.agent.actions.base import Action, ActionContext, Prepared
from coffer.agent.actions.common import ASSET_CLASSES, CLASS_PL, load_profile_target
from coffer.agent.schemas import (
    DISCLAIMER,
    Fact,
    Finding,
    Recommendation,
    ReportDraft,
    Table,
    TableColumn,
)
from coffer.agent.tools.user_data import CLASS_LABELS
from coffer.agent.validator import Seen
from coffer.analytics.allocation import allocation_gap, max_position_share, share_pct

EMPTY_PORTFOLIO = "Portfel jest pusty. Dodaj pozycje, aby uzyskać analizę."
REBALANCE_PP = Decimal(10)  # classes off target by at least this many p.p. get a recommendation
CONCENTRATION_PCT = Decimal(25)  # one position above this share of the portfolio is a warning


class NoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _label(asset_class: str) -> str:
    return CLASS_PL.get(asset_class, CLASS_LABELS.get(asset_class, asset_class))


def _pct(value: Decimal | None) -> str:
    return "—" if value is None else f"{value:.1f}"


def prepare(ctx: ActionContext, params: NoParams) -> Prepared:
    portfolio = ctx.call("get_portfolio", {})
    if not portfolio["positions"]:
        return Prepared(no_data=EMPTY_PORTFOLIO)
    pt = load_profile_target(ctx)
    has_profile, risk, horizon, target = pt.has_profile, pt.risk, pt.horizon, pt.target
    net_worth = ctx.call("get_net_worth", {})

    current = {c["asset_class"]: Decimal(c["share_pct"]) for c in portfolio["classes"]}
    target_pct = {c["asset_class"]: Decimal(c["target_pct"]) for c in target["classes"]}
    gaps = allocation_gap(current, target_pct)
    values = [Decimal(p["value"]) for p in portfolio["positions"]]
    largest = max_position_share(values)
    net = Decimal(net_worth["net_worth"])
    cash_share = share_pct(Decimal(net_worth["cash_balance"]), net)

    facts = [
        Fact(label="Wartość portfela", value=portfolio["total_value"], kind="money"),
        Fact(label="Liczba pozycji", value=str(len(values)), kind="number"),
        Fact(label="Największa pozycja", value=_pct(largest), kind="percent"),
        Fact(label="Udział gotówki w majątku", value=_pct(cash_share), kind="percent"),
    ]
    rows = [
        {
            "asset_class": _label(g.asset_class),
            "current": f"{g.current_pct:.1f}",
            "target": f"{g.target_pct:.1f}",
            "gap": f"{g.gap_pp:.1f}",
        }
        for g in gaps
    ]
    table = Table(
        id="allocation",
        title="Alokacja: obecna i docelowa",
        columns=[
            TableColumn(key="asset_class", label="Klasa aktywów", kind="text"),
            TableColumn(key="current", label="Obecnie (%)", kind="percent"),
            TableColumn(key="target", label="Cel (%)", kind="percent"),
            TableColumn(key="gap", label="Różnica (p.p.)", kind="number"),
        ],
        rows=rows,
    )
    context: dict[str, Any] = {
        "fakty": {f.label: f.value for f in facts},
        "alokacja": rows,
        "pozycje": [
            {k: p[k] for k in ("symbol", "asset_class", "share_pct", "gain_pct")}
            for p in portfolio["positions"]
        ],
        "profil": {"ryzyko": risk, "horyzont": horizon},
        "profil_domyslny": not has_profile,
        "portfel_kompletny": portfolio["complete"],
    }
    snapshot: dict[str, Any] = {
        "total_value": portfolio["total_value"],
        "positions": len(values),
        "max_position_pct": None if largest is None else str(largest),
        "cash_share_pct": None if cash_share is None else str(cash_share),
        "complete": portfolio["complete"],
        "has_profile": has_profile,
        "risk": risk,
        "horizon": horizon,
        "allocation": [
            {
                "asset_class": g.asset_class,
                "current": str(g.current_pct),
                "target": str(g.target_pct),
            }
            for g in gaps
        ],
    }
    return Prepared(
        facts=facts,
        tables=[table],
        context=context,
        snapshot=snapshot,
        profile_snapshot=pt.profile_snapshot,
    )


def fallback(prepared: Prepared, params: NoParams) -> ReportDraft:
    """Deterministic review: rebalance towards the target, concentration, missing profile."""
    snap = prepared.snapshot
    findings = [
        Finding(
            title="Wartość i struktura portfela",
            detail=f"Portfel liczy {snap['positions']} poz. o łącznej wartości "
            f"{snap['total_value']} PLN.",
            refers_to="portfolio",
            value=snap["total_value"],
        )
    ]
    largest = snap["max_position_pct"]
    if largest is not None and Decimal(largest) > CONCENTRATION_PCT:
        findings.append(
            Finding(
                title="Duża koncentracja portfela",
                detail=f"Największa pozycja to {largest}% portfela (próg ostrzeżenia: "
                f"{CONCENTRATION_PCT}%). Rozważ rozłożenie ryzyka na więcej instrumentów.",
                refers_to="portfolio",
                value=largest,
            )
        )
    if not snap["has_profile"]:
        findings.append(
            Finding(
                title="Brak profilu inwestycyjnego",
                detail="Cel alokacji wyznaczono dla profilu domyślnego (ryzyko średnie, horyzont "
                "średni). Uzupełnij profil inwestycyjny, aby dopasować cel do siebie.",
                refers_to="profile",
            )
        )

    off = [
        a
        for a in snap["allocation"]
        if abs(Decimal(a["target"]) - Decimal(a["current"])) >= REBALANCE_PP
    ]
    recommendations: list[Recommendation] = []
    for a in off[:5]:  # `allocation` is sorted by the size of the gap
        current, target = Decimal(a["current"]), Decimal(a["target"])
        verb = "Zwiększ" if target > current else "Zmniejsz"
        recommendations.append(
            Recommendation(
                title=f"{verb} udział: {_label(a['asset_class'])}",
                detail=f"Obecnie {current:.1f}%, cel {target:.1f}% "
                f"(różnica {abs(target - current):.1f} p.p.).",
                asset_class=a["asset_class"],
            )
        )
    if not off:
        findings.append(
            Finding(
                title="Alokacja zbliżona do celu",
                detail=f"Żadna klasa aktywów nie odbiega od celu o {REBALANCE_PP} p.p. lub więcej.",
                refers_to="calc",
            )
        )
    if not snap["has_profile"]:
        recommendations.append(
            Recommendation(
                title="Uzupełnij profil inwestycyjny",
                detail="Profil pozwoli dopasować docelową alokację do Twojego ryzyka i horyzontu.",
            )
        )

    risks = ["Cel alokacji to uproszczona reguła, a nie indywidualna porada."]
    if not snap["complete"]:
        risks.append(
            "Wycena portfela jest niepełna (brak notowań lub kursów), więc udziały są przybliżone."
        )
    headline = f"Portfel o wartości {snap['total_value']} PLN: " + (
        f"{len(off)} klas(y) wymaga korekty." if off else "struktura zgodna z celem."
    )
    return ReportDraft(
        headline=headline,
        findings=findings[:6],
        recommendations=recommendations[:5],
        risks=risks,
    )


def check(draft: ReportDraft, prepared: Prepared, seen: Seen) -> list[str]:
    errors: list[str] = []
    for i, r in enumerate(draft.recommendations, 1):
        if r.asset_class is not None and r.asset_class not in ASSET_CLASSES:
            errors.append(f"Rekomendacja {i}: nieznana klasa aktywów {r.asset_class}.")
    return errors


PORTFOLIO_REVIEW = Action(
    id="portfolio_review",
    name="Analiza portfela",
    description="Porównuje strukturę Twojego portfela z docelową alokacją dla Twojego profilu "
    "inwestycyjnego i wskazuje koncentrację oraz możliwe korekty.",
    params_model=NoParams,
    params_ui=(),
    prompt_version="portfolio_review_v1",
    tools=(
        "get_portfolio",
        "get_investment_profile",
        "get_net_worth",
        "target_allocation",
        "get_price_history",
    ),
    draft_model=ReportDraft,
    disclaimer=DISCLAIMER,
    uses_user_data=True,
    uses_internet=True,
    prepare=prepare,
    fallback=fallback,
    check=check,
)
