"""purchase_impact: how a planned purchase changes the allocation (UC-07, F37)."""

from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from coffer.agent.actions.base import Action, ActionContext, Prepared
from coffer.agent.actions.common import (
    ASSET_CLASSES,
    CLASS_PL,
    AssetClass,
    load_profile_target,
)
from coffer.agent.schemas import (
    DISCLAIMER,
    Fact,
    Finding,
    ParamSpec,
    Recommendation,
    ReportDraft,
    Table,
    TableColumn,
)
from coffer.agent.validator import Seen
from coffer.analytics.planning import previous_month
from coffer.core.money import quantize
from coffer.market import service as market_service

CONCENTRATION_PP = Decimal(10)  # a class this far above its target is a concentration warning
Currency = Literal["PLN", "EUR", "USD", "GBP", "CHF"]
Positive = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)]


class PurchaseParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_class: AssetClass
    symbol: str | None = None
    amount: Positive | None = None
    quantity: Positive | None = None
    price: Positive | None = None
    currency: Currency = "PLN"

    @field_validator("symbol")
    @classmethod
    def _symbol(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        sym = market_service.normalize_symbol(value)
        if sym is None:
            raise ValueError("Nieprawidłowy symbol.")
        return sym

    @model_validator(mode="after")
    def _one_size(self) -> Self:
        if (self.amount is None) == (self.quantity is None):
            raise ValueError("Podaj dokładnie jedno: kwotę albo liczbę sztuk.")
        if self.quantity is not None and self.symbol is None and self.price is None:
            raise ValueError("Przy liczbie sztuk podaj symbol albo cenę.")
        if self.amount is not None and self.price is not None:
            raise ValueError("Cena jest potrzebna tylko przy liczbie sztuk.")
        return self


def _label(asset_class: str) -> str:
    return CLASS_PL.get(asset_class, asset_class)


def _price_unknown(params: PurchaseParams) -> str:
    return f"Nie znamy ceny {params.symbol or 'tego instrumentu'}. Podaj cenę ręcznie."


def _unit_price(ctx: ActionContext, params: PurchaseParams) -> tuple[Decimal, str] | None:
    """Price per unit and its currency: a manual price wins over a quote."""
    if params.price is not None:
        return params.price, params.currency
    if params.symbol is None:
        return None
    out = ctx.try_call("get_quotes", {"symbols": [params.symbol]})
    if out is None:
        return None
    quotes = [q for q in out["quotes"] if q["symbol"].upper() == params.symbol]
    if not quotes:
        return None
    return Decimal(quotes[0]["price"]), quotes[0]["currency"]


def prepare(ctx: ActionContext, params: PurchaseParams) -> Prepared:
    if params.amount is not None:
        raw, currency = params.amount, params.currency
    else:
        assert params.quantity is not None
        found = _unit_price(ctx, params)
        if found is None:
            return Prepared(no_data=_price_unknown(params))
        price, currency = found
        raw = price * params.quantity
    rate = Decimal(1)
    if currency != "PLN":
        fx = ctx.try_call("get_fx_rate", {"from_ccy": currency, "to_ccy": "PLN"})
        if fx is None:
            return Prepared(no_data=f"Nie znamy kursu {currency}/PLN. Podaj kwotę w PLN.")
        rate = Decimal(fx["rate"])
    amount_pln = quantize(raw * rate)
    if amount_pln <= 0:
        return Prepared(no_data="Kwota zakupu po przeliczeniu jest zbyt mała.")

    sim = ctx.call(
        "simulate_purchase", {"asset_class": params.asset_class, "amount": str(amount_pln)}
    )
    pt = load_profile_target(ctx)
    has_profile, risk, horizon, target = pt.has_profile, pt.risk, pt.horizon, pt.target
    target_pct = {c["asset_class"]: c["target_pct"] for c in target["classes"]}
    month = previous_month(ctx.now.date())
    surplus = ctx.call("get_month_analysis", {"month": month})["surplus"]
    within = amount_pln <= Decimal(surplus)

    before = {s["asset_class"]: s["share_pct"] for s in sim["before"]}
    after = {s["asset_class"]: s["share_pct"] for s in sim["after"]}
    classes = sorted(set(before) | set(after), key=lambda c: (-Decimal(after.get(c, "0")), c))
    rows = [
        {
            "asset_class": _label(c),
            "before": before.get(c, "0.0"),
            "after": after.get(c, "0.0"),
            "change": f"{Decimal(after.get(c, '0.0')) - Decimal(before.get(c, '0.0')):.1f}",
        }
        for c in classes
    ]
    table = Table(
        id="allocation_change",
        title="Alokacja przed i po zakupie",
        columns=[
            TableColumn(key="asset_class", label="Klasa aktywów", kind="text"),
            TableColumn(key="before", label="Przed (%)", kind="percent"),
            TableColumn(key="after", label="Po (%)", kind="percent"),
            TableColumn(key="change", label="Zmiana (p.p.)", kind="number"),
        ],
        rows=rows,
    )
    facts = [
        Fact(label="Kwota zakupu (PLN)", value=f"{amount_pln:.2f}", kind="money"),
        Fact(label=f"Nadwyżka w {month}", value=surplus, kind="money"),
        Fact(label="Kwota w granicach nadwyżki", value="tak" if within else "nie", kind="text"),
        Fact(label="Wartość portfela przed", value=sim["total_before"], kind="money"),
        Fact(label="Wartość portfela po", value=sim["total_after"], kind="money"),
    ]
    snapshot: dict[str, Any] = {
        "asset_class": params.asset_class,
        "symbol": params.symbol,
        "amount_pln": f"{amount_pln:.2f}",
        "surplus": surplus,
        "surplus_month": month,
        "within_surplus": within,
        "new_class": sim["new_class"],
        "has_profile": has_profile,
        "risk": risk,
        "horizon": horizon,
        "before_pct": before.get(params.asset_class, "0.0"),
        "after_pct": after.get(params.asset_class, "0.0"),
        "target_pct": target_pct.get(params.asset_class, "0.0"),
        "total_before": sim["total_before"],
        "total_after": sim["total_after"],
        "allocation": rows,
    }
    context: dict[str, Any] = {
        "zakup": {
            "klasa": params.asset_class,
            "symbol": params.symbol,
            "kwota_pln": f"{amount_pln:.2f}",
            "nowa_klasa_w_portfelu": sim["new_class"],
        },
        "fakty": {f.label: f.value for f in facts},
        "alokacja": rows,
        "cel_dla_klasy_pct": snapshot["target_pct"],
        "cel_alokacji": target["classes"],
        "profil": {"ryzyko": risk, "horyzont": horizon},
        "profil_domyslny": not has_profile,
    }
    return Prepared(
        facts=facts,
        tables=[table],
        context=context,
        snapshot=snapshot,
        profile_snapshot=pt.profile_snapshot,
    )


def fallback(prepared: Prepared, params: PurchaseParams) -> ReportDraft:
    """Rule-based assessment: closer to or further from the target, concentration, profile."""
    s = prepared.snapshot
    label = _label(s["asset_class"])
    before, after, target = (
        Decimal(s["before_pct"]),
        Decimal(s["after_pct"]),
        Decimal(s["target_pct"]),
    )
    closer = abs(target - after) < abs(target - before)
    findings = [
        Finding(
            title="Wpływ na alokację",
            detail=f"Udział klasy {label} zmieni się z {before}% do {after}% "
            f"(cel dla Twojego profilu: {target}%). Zakup "
            + ("zbliża portfel do celu." if closer else "oddala portfel od celu."),
            refers_to="portfolio",
            value=s["after_pct"],
        ),
        Finding(
            title="Zakup a nadwyżka",
            detail=f"Kwota zakupu {s['amount_pln']} PLN "
            + (
                f"mieści się w nadwyżce z {s['surplus_month']} ({s['surplus']} PLN)."
                if s["within_surplus"]
                else f"przekracza nadwyżkę z {s['surplus_month']} ({s['surplus']} PLN)."
            ),
            refers_to="budget",
            value=s["amount_pln"],
        ),
    ]
    recommendations: list[Recommendation] = []
    risks = ["Ocena opiera się na uproszczonej regule alokacji, a nie na indywidualnej poradzie."]
    if s["new_class"]:
        findings.append(
            Finding(
                title="Nowa klasa aktywów",
                detail=f"W portfelu nie ma jeszcze klasy {label}; zakup ją otworzy.",
                refers_to="portfolio",
            )
        )
    if after > target + CONCENTRATION_PP:
        risks.append(
            f"Po zakupie klasa {label} stanowiłaby {after}% portfela, więcej niż cel {target}% "
            f"o ponad {CONCENTRATION_PP} p.p. (ryzyko koncentracji)."
        )
        recommendations.append(
            Recommendation(
                title=f"Rozważ mniejszą kwotę lub inną klasę niż {label}",
                detail=f"Udział {after}% przekraczałby cel {target}% "
                f"o ponad {CONCENTRATION_PP} p.p.",
                asset_class=s["asset_class"],
            )
        )
    elif closer:
        recommendations.append(
            Recommendation(
                title=f"Zakup klasy {label} jest zgodny z kierunkiem celu",
                detail=f"Po zakupie udział {after}% przy celu {target}%.",
                asset_class=s["asset_class"],
                amount=s["amount_pln"],
            )
        )
    if not s["within_surplus"]:
        recommendations.append(
            Recommendation(
                title="Rozłóż zakup w czasie",
                detail=f"Kwota {s['amount_pln']} PLN przekracza nadwyżkę {s['surplus']} PLN.",
                amount=s["amount_pln"],
            )
        )
    if not s["has_profile"]:
        recommendations.append(
            Recommendation(
                title="Uzupełnij profil inwestycyjny",
                detail="Cel alokacji wyznaczono dla profilu domyślnego (ryzyko średnie, "
                "horyzont średni). Profil pozwoli dopasować ocenę do Ciebie (UC-05).",
            )
        )
    return ReportDraft(
        headline=f"Zakup za {s['amount_pln']} PLN ({label}) "
        + ("zbliża portfel do celu." if closer else "oddala portfel od celu."),
        findings=findings[:6],
        recommendations=recommendations[:5],
        risks=risks[:5],
    )


def check(draft: ReportDraft, prepared: Prepared, seen: Seen) -> list[str]:
    errors: list[str] = []
    for i, r in enumerate(draft.recommendations, 1):
        if r.asset_class is not None and r.asset_class not in ASSET_CLASSES:
            errors.append(f"Rekomendacja {i}: nieznana klasa aktywów {r.asset_class}.")
    return errors


PURCHASE_IMPACT = Action(
    id="purchase_impact",
    name="Wpływ zakupu na portfel",
    description="Pokazuje, jak planowany zakup zmieni podział portfela na klasy aktywów, "
    "czy zbliża go do celu i czy mieści się w ostatniej nadwyżce.",
    params_model=PurchaseParams,
    params_ui=(
        ParamSpec(
            name="asset_class",
            label="Klasa aktywów",
            kind="select",
            required=True,
            options=ASSET_CLASSES,
        ),
        ParamSpec(name="symbol", label="Symbol (opcjonalnie)", kind="symbol"),
        ParamSpec(
            name="amount",
            label="Kwota zakupu",
            kind="amount",
            help="Podaj kwotę albo liczbę sztuk.",
        ),
        ParamSpec(
            name="quantity",
            label="Liczba sztuk",
            kind="quantity",
            help="Wymaga symbolu (cena z notowania) albo ceny.",
        ),
        ParamSpec(name="price", label="Cena jednostkowa (opcjonalnie)", kind="amount"),
        ParamSpec(
            name="currency",
            label="Waluta",
            kind="select",
            default="PLN",
            options=("PLN", "EUR", "USD", "GBP", "CHF"),
        ),
    ),
    prompt_version="purchase_impact_v1",
    tools=(
        "simulate_purchase",
        "get_portfolio",
        "get_investment_profile",
        "target_allocation",
        "get_quotes",
        "get_fx_rate",
        "get_month_analysis",
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
