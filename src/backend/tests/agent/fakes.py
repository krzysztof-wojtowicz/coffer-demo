"""A test action and registry for the engine tests (the real catalogue is tested separately)."""

from pydantic import BaseModel, ConfigDict

from coffer.agent.actions.base import Action, ActionContext, Prepared
from coffer.agent.schemas import Fact, Finding, ReportDraft
from coffer.agent.tools.registry import Tool, ToolContext, ToolFailure, default_registry
from coffer.agent.validator import Seen


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid")
    empty: bool = False
    explode: bool = False


class NoInput(BaseModel):
    pass


class LinksOut(BaseModel):
    links: list[dict[str, str]]


def _links(ctx: ToolContext, args: NoInput) -> LinksOut:
    return LinksOut(links=[{"title": "Hasło", "url": "https://pl.wikipedia.org/wiki/Akcja"}])


def _boom(ctx: ToolContext, args: NoInput) -> LinksOut:
    raise ToolFailure("Źródło niedostępne.")


def _crash(ctx: ToolContext, args: NoInput) -> LinksOut:
    raise ZeroDivisionError("secret internals")


def registry():
    reg = default_registry()
    reg.register(Tool("links", "Linki", NoInput, _links, group="market", uses_internet=True))
    reg.register(Tool("boom", "Zawsze błąd", NoInput, _boom, group="calc"))
    reg.register(Tool("crash", "Wyjątek", NoInput, _crash, group="calc"))
    return reg


def prepare(ctx: ActionContext, params: Params) -> Prepared:
    if params.explode:
        raise RuntimeError("prepare exploded")
    if params.empty:
        return Prepared(no_data="Brak danych.")
    out = ctx.call("target_allocation", {"risk": "low", "horizon": "medium"})
    return Prepared(
        facts=[Fact(label="Klasy", value=str(len(out["classes"])), kind="number")],
        context={"cel": out},
        snapshot={"classes": len(out["classes"])},
    )


def fallback(prepared: Prepared, params: Params) -> ReportDraft:
    return ReportDraft(
        headline="Wynik regułowy",
        findings=[Finding(title="Reguły", detail="Bez AI.", refers_to="calc")],
    )


def check(draft: ReportDraft, prepared: Prepared, seen: Seen) -> list[str]:
    return ["Zakazane słowo."] if "zakazane" in draft.headline else []


ACTION = Action(
    id="test_action",
    name="Akcja testowa",
    description="Tylko do testów.",
    params_model=Params,
    params_ui=(),
    prompt_version="portfolio_review_v1",
    tools=("target_allocation", "links", "boom", "crash"),
    draft_model=ReportDraft,
    disclaimer="Test.",
    uses_user_data=False,
    uses_internet=False,
    prepare=prepare,
    fallback=fallback,
    check=check,
    max_steps=4,
)
