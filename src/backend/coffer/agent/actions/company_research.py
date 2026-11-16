"""company_research: public information about a company, no user data at all (UC-13, F34, F35)."""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from coffer.agent.actions.base import Action, ActionContext, Prepared
from coffer.agent.schemas import (
    Fact,
    Finding,
    ParamSpec,
    ReportDraft,
    Source,
    Table,
    TableColumn,
)
from coffer.agent.validator import Seen

NOT_FOUND = "Nie znaleziono spółki. Sprawdź nazwę lub ticker."
UNAVAILABLE = "Dane rynkowe są chwilowo niedostępne."
DISCLAIMER_RESEARCH = "Informacje mają charakter poglądowy i nie są rekomendacją; sprawdź źródła."
COMPANY_TYPES = {"equity", "etf", "stock"}
_QUERY = re.compile(r"[\w .&-]+")
USER_DATA_SECTIONS = {"budget", "profile", "portfolio"}


class CompanyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=60)

    @field_validator("query")
    @classmethod
    def _query(cls, value: str) -> str:
        value = value.strip()
        if not value or not _QUERY.fullmatch(value):
            raise ValueError("Nazwa spółki może zawierać litery, cyfry, spacje oraz . & -.")
        return value


def _date(value: str | None) -> str:
    return value[:10] if value else "—"


def prepare(ctx: ActionContext, params: CompanyParams) -> Prepared:
    found = ctx.call("search_symbol", {"query": params.query})["matches"]
    companies = [m for m in found if (m["type"] or "").casefold() in COMPANY_TYPES]
    if not companies:
        return Prepared(no_data=NOT_FOUND)
    match, others = companies[0], companies[1:]
    symbol = match["symbol"]
    profile = ctx.try_call("get_company_profile", {"symbol": symbol})
    quotes = ctx.try_call("get_quotes", {"symbols": [symbol]})
    news = (ctx.try_call("get_company_news", {"symbol": symbol, "limit": 5}) or {"news": []})[
        "news"
    ]
    history = ctx.try_call("get_price_history", {"symbol": symbol, "period": "1y"})
    quote = quotes["quotes"][0] if quotes and quotes["quotes"] else None
    if profile is None and quote is None:
        return Prepared(no_data=UNAVAILABLE)

    facts: list[Fact] = []
    if quote:
        facts.append(Fact(label="Cena", value=f"{quote['price']} {quote['currency']}", kind="text"))
    stats = history["price_stats"] if history else None
    if stats:
        facts.append(Fact(label="Zmiana 1 r. (%)", value=stats["return_pct"], kind="percent"))
    if profile:
        ccy = profile["currency"] or ""
        if profile["market_cap"]:
            facts.append(
                Fact(
                    label="Kapitalizacja",
                    value=f"{profile['market_cap']} {ccy}".strip(),
                    kind="text",
                )
            )
        if profile["pe_ratio"]:
            facts.append(Fact(label="C/Z", value=profile["pe_ratio"], kind="number"))
        if profile["dividend_yield"]:
            facts.append(
                Fact(label="Stopa dywidendy (%)", value=profile["dividend_yield"], kind="percent")
            )
        if profile["sector"]:
            facts.append(Fact(label="Sektor", value=profile["sector"], kind="text"))
    if others:
        facts.append(
            Fact(
                label="Inne pasujące symbole",
                value=", ".join(m["symbol"] for m in others[:4]),
                kind="text",
            )
        )

    sources: list[Source] = []
    if profile:
        sources.append(
            Source(
                title=f"Profil: {profile['name'] or symbol}",
                url=profile["source_url"],
                publisher="Yahoo Finance",
                fetched_at=profile["fetched_at"],
            )
        )
    for n in news:
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
    tables = []
    if news:
        tables.append(
            Table(
                id="news",
                title="Najnowsze wiadomości",
                columns=[
                    TableColumn(key="date", label="Data", kind="date"),
                    TableColumn(key="title", label="Tytuł", kind="text"),
                    TableColumn(key="publisher", label="Wydawca", kind="text"),
                ],
                rows=[
                    {
                        "date": _date(n["published_at"]),
                        "title": n["title"],
                        "publisher": n["publisher"],
                    }
                    for n in news
                ],
            )
        )
    name = (profile or {}).get("name") or match["name"] or symbol
    context: dict[str, Any] = {
        "zapytanie": params.query,
        "trafienie": match,
        "fakty": {f.label: f.value for f in facts},
        "profil": profile,
        "notowanie": quote,
        "statystyki_cen_1r": stats,
        "wiadomosci": news,
    }
    snapshot: dict[str, Any] = {
        "query": params.query,
        "symbol": symbol,
        "name": name,
        "sector": (profile or {}).get("sector"),
        "summary": (profile or {}).get("summary"),
        "news": news,
    }
    return Prepared(facts=facts, tables=tables, sources=sources, context=context, snapshot=snapshot)


def fallback(prepared: Prepared, params: CompanyParams) -> ReportDraft:
    s = prepared.snapshot
    findings: list[Finding] = []
    if s["summary"]:
        text = s["summary"] if len(s["summary"]) <= 300 else s["summary"][:299].rstrip() + "…"
        findings.append(Finding(title=f"Profil: {s['name']}", detail=text, refers_to="market"))
    for n in s["news"][:3]:
        detail = f"{_date(n['published_at'])}, {n['publisher']}."
        if n["summary"]:
            detail = f"{n['summary']} ({detail})"
        findings.append(Finding(title=n["title"], detail=detail, refers_to="market"))
    if not findings:
        findings.append(
            Finding(
                title="Brak opisu i wiadomości",
                detail="Źródła nie zwróciły opisu ani wiadomości o spółce.",
                refers_to="market",
            )
        )
    sector = f", sektor: {s['sector']}" if s["sector"] else ""
    return ReportDraft(
        headline=f"{s['name']} ({s['symbol']}){sector}",
        findings=findings,
        risks=["Dane pochodzą z publicznych źródeł i mogą być opóźnione lub niepełne."],
    )


def check(draft: ReportDraft, prepared: Prepared, seen: Seen) -> list[str]:
    errors: list[str] = []
    if not draft.source_urls:
        errors.append("Podaj co najmniej jeden adres źródła w polu source_urls.")
    for i, f in enumerate(draft.findings, 1):
        if f.refers_to in USER_DATA_SECTIONS:
            errors.append(f"Wniosek {i}: pole refers_to musi dotyczyć rynku (market albo calc).")
    return errors


COMPANY_RESEARCH = Action(
    id="company_research",
    name="Informacje o spółce",
    description="Zbiera publiczne informacje o spółce lub ETF-ie: profil, notowanie, "
    "wskaźniki i najnowsze wiadomości, każdą ze źródłem i datą.",
    params_model=CompanyParams,
    params_ui=(
        ParamSpec(
            name="query",
            label="Nazwa lub ticker",
            kind="text",
            required=True,
            help="Np. PKO BP, AAPL.",
        ),
    ),
    prompt_version="company_research_v1",
    tools=("get_company_news", "get_price_history", "get_wikipedia_summary", "get_quotes"),
    draft_model=ReportDraft,
    disclaimer=DISCLAIMER_RESEARCH,
    uses_user_data=False,
    uses_internet=True,
    prepare=prepare,
    fallback=fallback,
    check=check,
)
