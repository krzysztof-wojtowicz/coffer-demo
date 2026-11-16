"""investment_ideas: instruments that fit the profile, the allocation gap and the amount (UC-06)."""

from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from coffer.agent.actions.base import Action, ActionContext, Prepared
from coffer.agent.actions.common import (
    ASSET_CLASSES,
    CLASS_PL,
    load_profile_target,
    plural,
)
from coffer.agent.schemas import (
    DISCLAIMER,
    Fact,
    Finding,
    ParamSpec,
    Recommendation,
    ReportDraft,
    Source,
)
from coffer.agent.validator import Seen
from coffer.analytics.planning import previous_month
from coffer.core.months import MonthStr

NO_SURPLUS = "Brak nadwyżki w wybranym miesiącu. Podaj kwotę ręcznie."
PICKS = 3
MAX_RISK = {"low": 2, "medium": 3, "high": 5}
TARGET_RISK = {"low": Decimal("1.5"), "medium": Decimal(3), "high": Decimal(4)}
RISK_PL = {"low": "niski", "medium": "umiarkowany", "high": "wysoki"}
# Profile classes (plural names) -> portfolio classes.
PROFILE_CLASS = {
    "stocks": "stock",
    "bonds": "bond",
    "deposit": "cash",
    "cash": "cash",
    "etf": "etf",
    "crypto": "crypto",
    "real_estate": "real_estate",
}


class IdeasParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    month: MonthStr | None = None
    amount: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)] | None = None
    asset_class: (
        Literal["stock", "etf", "bond", "real_estate", "commodity", "crypto", "cash"] | None
    ) = None


def max_risk(risk: str, horizon: str) -> int:
    cap = MAX_RISK.get(risk, 3)
    return min(cap, 2) if horizon == "short" else cap


def _score(
    inst: dict[str, Any],
    risk: str,
    preferred: set[str],
    gaps: dict[str, Decimal],
    held: set[str],
) -> Decimal:
    score = -abs(Decimal(inst["risk_level"]) - TARGET_RISK.get(risk, Decimal(3))) * 2
    if inst["asset_class"] in preferred:
        score += 2
    score += gaps.get(inst["asset_class"], Decimal(0)) / 10  # underweight classes first
    if inst["symbol"] and inst["symbol"] in held:
        score -= 3
    return score


def _rationale(inst: dict[str, Any], risk: str, preferred: set[str], gap: Decimal) -> str:
    cls = CLASS_PL.get(inst["asset_class"], inst["asset_class"])
    parts = [inst["description"]]
    if gap > 0:
        parts.append(f"Klasa „{cls}” jest poniżej celu o {gap:.1f} p.p.")
    if inst["asset_class"] in preferred:
        parts.append("To jedna z preferowanych przez Ciebie klas aktywów.")
    parts.append(
        f"Ryzyko {inst['risk_level']}/5 pasuje do profilu: {RISK_PL.get(risk, 'umiarkowany')}."
    )
    return " ".join(parts)


def _picks(
    universe: list[dict[str, Any]],
    risk: str,
    preferred: set[str],
    gaps: dict[str, Decimal],
    held: set[str],
) -> list[dict[str, Any]]:
    ranked = sorted(universe, key=lambda i: _score(i, risk, preferred, gaps, held), reverse=True)
    chosen: list[dict[str, Any]] = []
    for inst in ranked:  # first pass: distinct asset classes
        if inst["asset_class"] not in {c["asset_class"] for c in chosen}:
            chosen.append(inst)
        if len(chosen) == PICKS:
            break
    for inst in ranked:  # second pass: fill up
        if len(chosen) == PICKS:
            break
        if inst not in chosen:
            chosen.append(inst)
    return [
        {
            "name": i["name"],
            "symbol": i["symbol"],
            "asset_class": i["asset_class"],
            "risk_level": i["risk_level"],
            "rationale": _rationale(i, risk, preferred, gaps.get(i["asset_class"], Decimal(0))),
            "source_url": i["source_url"],
        }
        for i in chosen
    ]


def prepare(ctx: ActionContext, params: IdeasParams) -> Prepared:
    month = params.month or previous_month(ctx.now.date())
    if params.amount is not None:
        amount, source = params.amount, "podana kwota"
    else:
        overview = ctx.call("get_months_overview", {"month": month, "count": 1})
        amount, source = Decimal(overview["months"][0]["surplus"]), f"nadwyżka z {month}"
        if amount <= 0:
            return Prepared(no_data=NO_SURPLUS)

    pt = load_profile_target(ctx)
    profile, has_profile, risk, horizon = pt.profile, pt.has_profile, pt.risk, pt.horizon
    target = pt.target
    cap = max_risk(risk, horizon)
    portfolio = ctx.call("get_portfolio", {})
    universe_out = ctx.call("get_instrument_universe", {})

    current = {c["asset_class"]: Decimal(c["share_pct"]) for c in portfolio["classes"]}
    gaps = {
        c["asset_class"]: Decimal(c["target_pct"]) - current.get(c["asset_class"], Decimal(0))
        for c in target["classes"]
    }
    preferred: set[str] = {
        PROFILE_CLASS.get(str(c), str(c)) for c in (profile.get("preferred_classes") or [])
    }
    held: set[str] = {str(p["symbol"]) for p in portfolio["positions"] if p["symbol"]}
    universe = [
        i
        for i in universe_out["instruments"]
        if i["risk_level"] <= cap
        and (params.asset_class is None or i["asset_class"] == params.asset_class)
    ]
    if not universe:
        return Prepared(no_data="Brak instrumentów spełniających kryteria. Zmień klasę aktywów.")
    picks = _picks(universe, risk, preferred, gaps, held)

    sources: list[Source] = []
    news: list[dict[str, Any]] = []
    market_news = ctx.try_call("get_market_news", {"limit": 5})  # optional
    for n in (market_news or {"news": []})["news"]:
        news.append({"title": n["title"], "url": n["url"], "published_at": n["published_at"]})
        if n["url"]:
            sources.append(
                Source(
                    title=n["title"],
                    url=n["url"],
                    publisher=n["publisher"],
                    published_at=n["published_at"],
                    fetched_at=n["fetched_at"],
                )
            )

    facts = [
        Fact(label="Kwota do zainwestowania", value=f"{amount:.2f}", kind="money"),
        Fact(label="Źródło kwoty", value=source, kind="text"),
        Fact(label="Maksymalny poziom ryzyka (1-5)", value=str(cap), kind="number"),
    ]
    gap_rows = [
        {"asset_class": CLASS_PL.get(k, k), "gap_pp": f"{v:.1f}"} for k, v in sorted(gaps.items())
    ]
    context: dict[str, Any] = {
        "fakty": {f.label: f.value for f in facts},
        "profil": {"ryzyko": risk, "horyzont": horizon, "preferowane_klasy": sorted(preferred)},
        "profil_domyslny": not has_profile,
        "udzialy_klas_w_portfelu_pct": {k: str(v) for k, v in current.items()},
        "luka_wzgledem_celu_pp": gap_rows,
        "dopuszczalne_instrumenty": universe,
        "wiadomosci_rynkowe": news,
    }
    snapshot: dict[str, Any] = {
        "month": month,
        "amount": f"{amount:.2f}",
        "amount_source": source,
        "max_risk": cap,
        "risk": risk,
        "horizon": horizon,
        "has_profile": has_profile,
        "asset_class": params.asset_class,
        "picks": picks,
        "min_recommendations": 1,
        "allowed": [
            {k: i[k] for k in ("name", "symbol", "asset_class", "risk_level", "source_url")}
            for i in universe
        ],
    }
    return Prepared(
        facts=facts,
        sources=sources,
        context=context,
        snapshot=snapshot,
        profile_snapshot=pt.profile_snapshot,
    )


def fallback(prepared: Prepared, params: IdeasParams) -> ReportDraft:
    s = prepared.snapshot
    findings = [
        Finding(
            title="Kwota do zainwestowania",
            detail=f"Do zainwestowania jest {s['amount']} PLN ({s['amount_source']}). "
            f"Maksymalny poziom ryzyka dla Twojego profilu to {s['max_risk']}/5.",
            refers_to="budget",
            value=s["amount"],
        )
    ]
    if not s["has_profile"]:
        findings.append(
            Finding(
                title="Brak profilu inwestycyjnego",
                detail="Użyto profilu domyślnego (ryzyko średnie, horyzont średni). "
                "Uzupełnij profil, aby propozycje były trafniejsze.",
                refers_to="profile",
            )
        )
    recs = [
        Recommendation(
            title=p["name"],
            detail=p["rationale"],
            symbol=p["symbol"],
            asset_class=p["asset_class"],
            risk_level=p["risk_level"],
            source_url=p["source_url"],
        )
        for p in s["picks"]
    ]
    return ReportDraft(
        headline=f"Propozycje dopasowane do profilu na kwotę {s['amount']} PLN: "
        f"{len(recs)} {plural(len(recs), 'instrument', 'instrumenty', 'instrumentów')}.",
        findings=findings,
        recommendations=recs,
        risks=[
            "To propozycje z krótkiej, wbudowanej listy instrumentów, a nie pełny przegląd rynku.",
            "Ceny instrumentów mogą spadać, a przeszłe wyniki nie gwarantują przyszłych.",
        ],
    )


def _allowed(prepared: Prepared, rec: Recommendation) -> dict[str, Any] | None:
    allowed: list[dict[str, Any]] = prepared.snapshot["allowed"]
    key = (rec.symbol or "").strip().upper()
    if key:
        exact = next((i for i in allowed if i["symbol"] == key), None)
        if exact is not None:
            return exact
        # The model often drops or adds the exchange suffix ("CDR" vs "CDR.WA").
        base = key.split(".")[0]
        return next((i for i in allowed if i["symbol"] and i["symbol"].split(".")[0] == base), None)
    title = rec.title.strip().casefold()
    return next(
        (i for i in allowed if not i["symbol"] and i["name"].strip().casefold() == title), None
    )


def check(draft: ReportDraft, prepared: Prepared, seen: Seen) -> list[str]:
    """Recommendations must come from the allowed universe computed by code (a news item
    cannot talk the model into recommending an arbitrary ticker). No side effects."""
    errors: list[str] = []
    minimum = prepared.snapshot["min_recommendations"]
    if len(draft.recommendations) < minimum:
        errors.append("Podaj co najmniej jedną rekomendację.")
    for i, r in enumerate(draft.recommendations, 1):
        if _allowed(prepared, r) is None:
            errors.append(
                f"Rekomendacja {i}: instrument spoza dozwolonej listy "
                "(pole dopuszczalne_instrumenty)."
            )
    return errors


def finalize(draft: ReportDraft, prepared: Prepared) -> None:
    """Class, risk and link come from the universe, not from the model's answer."""
    for r in draft.recommendations:
        inst = _allowed(prepared, r)
        if inst is not None:
            r.symbol = inst["symbol"]
            r.asset_class = inst["asset_class"]
            r.risk_level = inst["risk_level"]
            r.source_url = inst["source_url"]


INVESTMENT_IDEAS = Action(
    id="investment_ideas",
    name="Nowe możliwości inwestycyjne",
    description="Proponuje instrumenty pasujące do Twojego profilu i luki w alokacji, "
    "na kwotę nadwyżki z miesiąca albo podaną ręcznie, ze źródłami rynkowymi.",
    params_model=IdeasParams,
    params_ui=(
        ParamSpec(
            name="month",
            label="Miesiąc nadwyżki",
            kind="month",
            help="Domyślnie ostatni pełny miesiąc.",
        ),
        ParamSpec(
            name="amount",
            label="Kwota do zainwestowania",
            kind="amount",
            help="Domyślnie nadwyżka z wybranego miesiąca.",
        ),
        ParamSpec(name="asset_class", label="Klasa aktywów", kind="select", options=ASSET_CLASSES),
    ),
    prompt_version="investment_ideas_v1",
    tools=(
        "get_quotes",
        "get_price_history",
        "get_company_news",
        "get_market_news",
        "simulate_purchase",
    ),
    draft_model=ReportDraft,
    disclaimer=DISCLAIMER,
    uses_user_data=True,
    uses_internet=True,
    prepare=prepare,
    fallback=fallback,
    check=check,
    finalize=finalize,
)
