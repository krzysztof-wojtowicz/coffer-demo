"""Market tools (E5-05, E5-07): quotes, FX, history, companies, news, search, Wikipedia.

Every result carries `fetched_at` and a `source_url` (the Yahoo Finance page), so the validator
can match sources cited by the model. Network problems become a Polish `ToolFailure`.
"""

from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import quote as url_quote

from pydantic import BaseModel, Field

from coffer.agent.schemas import is_http_url
from coffer.agent.tools.registry import Tool, ToolContext, ToolFailure
from coffer.analytics.market_stats import price_stats
from coffer.market import service as market_service

YAHOO_QUOTE_URL = "https://finance.yahoo.com/quote/"
UNAVAILABLE = "Dane rynkowe są chwilowo niedostępne"
MAX_POINTS = 30
SUMMARY_MAX = 600
NEWS_SUMMARY_MAX = 300


def yahoo_url(symbol: str) -> str:
    return YAHOO_QUOTE_URL + url_quote(symbol, safe="=^.-")


class QuotesInput(BaseModel):
    symbols: Annotated[list[str], Field(min_length=1, max_length=10)]


class QuoteOut(BaseModel):
    symbol: str
    name: str | None
    price: str
    currency: str
    change_pct: str | None
    as_of: str
    fetched_at: str
    source_url: str


class QuotesOut(BaseModel):
    quotes: list[QuoteOut]
    unknown: list[str]  # requested symbols without a quote


class FxRateInput(BaseModel):
    from_ccy: Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")]
    to_ccy: Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")]


class FxRateOut(BaseModel):
    from_ccy: str
    to_ccy: str
    rate: str
    fetched_at: str
    source_url: str


def _get_quotes(ctx: ToolContext, args: QuotesInput) -> QuotesOut:
    symbols = [s for s in (market_service.normalize_symbol(x) for x in args.symbols) if s]
    if not symbols:
        raise ToolFailure("Podane symbole są nieprawidłowe.")
    try:
        found = market_service.get_quotes(symbols, ctx.db)
    except market_service.MarketDataUnavailable as exc:
        raise ToolFailure(UNAVAILABLE) from exc
    quotes = [
        QuoteOut(
            symbol=q.symbol,
            name=q.name,
            price=f"{q.price:f}",
            currency=q.currency,
            change_pct=None if q.change_pct is None else f"{q.change_pct:.2f}",
            as_of=q.as_of.isoformat(),
            fetched_at=q.as_of.isoformat(),
            source_url=yahoo_url(q.symbol),
        )
        for q in found.values()
    ]
    return QuotesOut(quotes=quotes, unknown=[s for s in symbols if s.upper() not in found])


def _get_fx_rate(ctx: ToolContext, args: FxRateInput) -> FxRateOut:
    src, dst = args.from_ccy.upper(), args.to_ccy.upper()
    result = market_service.get_fx_quote(src, dst, ctx.db)
    if result is None:
        raise ToolFailure(f"Nie znamy kursu {src}/{dst}.")
    rate, fetched = result
    return FxRateOut(
        from_ccy=src,
        to_ccy=dst,
        rate=f"{rate:f}",
        fetched_at=fetched.isoformat(),
        source_url=yahoo_url(f"{src}{dst}=X"),
    )


# --- E5-07 ----------------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _cut(text: str | None, limit: int) -> str | None:
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _symbol(value: str) -> str:
    sym = market_service.normalize_symbol(value)
    if sym is None:
        raise ToolFailure("Podany symbol jest nieprawidłowy.")
    return sym


class PriceHistoryInput(BaseModel):
    symbol: Annotated[str, Field(min_length=1, max_length=20)]
    period: Literal["1mo", "3mo", "6mo", "1y", "5y"] = "1y"


class PricePointOut(BaseModel):
    date: str
    close: str


class PriceStatsOut(BaseModel):
    first: str
    last: str
    min: str
    max: str
    return_pct: str
    volatility_pct: str
    max_drawdown_pct: str


class PriceHistoryOut(BaseModel):
    symbol: str
    currency: str | None
    period: str
    points: list[PricePointOut]
    price_stats: PriceStatsOut | None
    fetched_at: str
    source_url: str


class SymbolInput(BaseModel):
    symbol: Annotated[str, Field(min_length=1, max_length=20)]


class CompanyProfileOut(BaseModel):
    symbol: str
    name: str | None
    sector: str | None
    industry: str | None
    country: str | None
    summary: str | None
    market_cap: str | None
    pe_ratio: str | None
    dividend_yield: str | None
    currency: str | None
    fetched_at: str
    source_url: str


class NewsInput(BaseModel):
    symbol: Annotated[str, Field(min_length=1, max_length=20)]
    limit: Annotated[int, Field(ge=1, le=5)] = 5


class MarketNewsInput(BaseModel):
    limit: Annotated[int, Field(ge=1, le=5)] = 5


class NewsItemOut(BaseModel):
    title: str
    summary: str | None
    publisher: str
    published_at: str | None
    url: str | None
    fetched_at: str


class NewsOut(BaseModel):
    symbol: str | None
    news: list[NewsItemOut]
    fetched_at: str


class SearchInput(BaseModel):
    query: Annotated[str, Field(min_length=1, max_length=60)]


class SymbolMatchOut(BaseModel):
    symbol: str
    name: str | None
    exchange: str | None
    type: str | None


class SearchOut(BaseModel):
    matches: list[SymbolMatchOut]
    fetched_at: str


class WikiOut(BaseModel):
    title: str
    extract: str
    url: str
    fetched_at: str


class EmptyIn(BaseModel):
    pass


class InstrumentOut(BaseModel):
    name: str
    symbol: str | None
    asset_class: str
    risk_level: int
    description: str
    source_url: str | None


class UniverseOut(BaseModel):
    instruments: list[InstrumentOut]
    fetched_at: str


def _get_price_history(ctx: ToolContext, args: PriceHistoryInput) -> PriceHistoryOut:
    sym = _symbol(args.symbol)
    history = market_service.get_price_history(sym, args.period)
    if history is None:
        raise ToolFailure(UNAVAILABLE)
    points = history.points
    if len(points) > MAX_POINTS:
        step = (len(points) - 1) / (MAX_POINTS - 1)
        points = [points[round(i * step)] for i in range(MAX_POINTS)]
    stats = price_stats(history.points)
    return PriceHistoryOut(
        symbol=history.symbol,
        currency=history.currency,
        period=args.period,
        points=[PricePointOut(date=d.isoformat(), close=f"{p:.2f}") for d, p in points],
        price_stats=None
        if stats is None
        else PriceStatsOut(
            first=f"{stats.first:.2f}",
            last=f"{stats.last:.2f}",
            min=f"{stats.min:.2f}",
            max=f"{stats.max:.2f}",
            return_pct=f"{stats.return_pct:.2f}",
            volatility_pct=f"{stats.volatility_pct:.2f}",
            max_drawdown_pct=f"{stats.max_drawdown_pct:.2f}",
        ),
        fetched_at=history.fetched_at.isoformat(),
        source_url=history.source_url,
    )


def _get_company_profile(ctx: ToolContext, args: SymbolInput) -> CompanyProfileOut:
    profile = market_service.get_company_profile(_symbol(args.symbol))
    if profile is None:
        raise ToolFailure(UNAVAILABLE)

    def num(value: object) -> str | None:
        return None if value is None else f"{value:f}"

    return CompanyProfileOut(
        symbol=profile.symbol,
        name=profile.name,
        sector=profile.sector,
        industry=profile.industry,
        country=profile.country,
        summary=_cut(profile.summary, SUMMARY_MAX),
        market_cap=num(profile.market_cap),
        pe_ratio=None if profile.pe_ratio is None else f"{profile.pe_ratio:.2f}",
        dividend_yield=None if profile.dividend_yield is None else f"{profile.dividend_yield:.2f}",
        currency=profile.currency,
        fetched_at=profile.fetched_at.isoformat(),
        source_url=profile.source_url,
    )


def _news_items(tips: list[market_service.MarketTip]) -> list[NewsItemOut]:
    return [
        NewsItemOut(
            title=t.title,
            summary=_cut(t.summary, NEWS_SUMMARY_MAX),
            publisher=t.source,
            published_at=None if t.published_at is None else t.published_at.isoformat(),
            url=t.url if is_http_url(t.url) else None,
            fetched_at=(t.fetched_at or datetime.now(UTC)).isoformat(),
        )
        for t in tips
    ]


def _get_company_news(ctx: ToolContext, args: NewsInput) -> NewsOut:
    sym = _symbol(args.symbol)
    tips = market_service.get_company_news(sym, args.limit)
    return NewsOut(symbol=sym, news=_news_items(tips), fetched_at=_now())


def _get_market_news(ctx: ToolContext, args: MarketNewsInput) -> NewsOut:
    tips = market_service.get_market_tips(args.limit)
    if not tips:
        raise ToolFailure(UNAVAILABLE)
    return NewsOut(symbol=None, news=_news_items(tips), fetched_at=_now())


def _search_symbol(ctx: ToolContext, args: SearchInput) -> SearchOut:
    matches = market_service.search_symbols(args.query, 5)
    return SearchOut(
        matches=[
            SymbolMatchOut(symbol=m.symbol, name=m.name, exchange=m.exchange, type=m.type)
            for m in matches
        ],
        fetched_at=_now(),
    )


def _get_wikipedia_summary(ctx: ToolContext, args: SearchInput) -> WikiOut:
    entry = market_service.get_wikipedia_summary(args.query)
    if entry is None:
        raise ToolFailure("Nie znaleziono hasła w Wikipedii albo źródło jest niedostępne.")
    return WikiOut(
        title=entry.title,
        extract=_cut(entry.extract, SUMMARY_MAX) or "",
        url=entry.url,
        fetched_at=entry.fetched_at.isoformat(),
    )


def _get_instrument_universe(ctx: ToolContext, args: EmptyIn) -> UniverseOut:
    return UniverseOut(
        instruments=[
            InstrumentOut(
                name=i.name,
                symbol=i.symbol,
                asset_class=i.asset_class,
                risk_level=i.risk_level,
                description=i.description,
                source_url=None if i.symbol is None else yahoo_url(i.symbol),
            )
            for i in market_service.get_instrument_universe()
        ],
        fetched_at=_now(),
    )


GET_QUOTES = Tool(
    name="get_quotes",
    description=(
        "Zwraca bieżące notowania (cena, waluta, zmiana dzienna w %) dla listy symboli "
        "(do 10, np. AAPL, CDR.WA, BTC-USD) wraz z czasem pobrania i adresem źródła. "
        "Symbole bez notowania trafiają do listy unknown."
    ),
    input_model=QuotesInput,
    func=_get_quotes,
    group="market",
    uses_internet=True,
)

GET_FX_RATE = Tool(
    name="get_fx_rate",
    description=(
        "Zwraca kurs wymiany walut (ile jednostek to_ccy za 1 from_ccy, kody trzyliterowe "
        "np. USD, PLN) wraz z czasem pobrania i adresem źródła."
    ),
    input_model=FxRateInput,
    func=_get_fx_rate,
    group="market",
    uses_internet=True,
)

GET_PRICE_HISTORY = Tool(
    name="get_price_history",
    description=(
        "Zwraca historię cen zamknięcia instrumentu (symbol, okres 1mo, 3mo, 6mo, 1y, 5y; "
        "do 30 punktów) oraz statystyki: zmianę w %, zmienność roczną, maksymalne obsunięcie."
    ),
    input_model=PriceHistoryInput,
    func=_get_price_history,
    group="market",
    uses_internet=True,
)

GET_COMPANY_PROFILE = Tool(
    name="get_company_profile",
    description=(
        "Zwraca profil spółki: nazwę, sektor, branżę, kraj, opis działalności, kapitalizację, "
        "wskaźnik C/Z i stopę dywidendy, z czasem pobrania i adresem źródła."
    ),
    input_model=SymbolInput,
    func=_get_company_profile,
    group="market",
    uses_internet=True,
)

GET_COMPANY_NEWS = Tool(
    name="get_company_news",
    description=(
        "Zwraca najnowsze wiadomości o spółce (symbol, do 5): tytuł, skrót, wydawca, data "
        "publikacji i adres artykułu."
    ),
    input_model=NewsInput,
    func=_get_company_news,
    group="market",
    uses_internet=True,
)

GET_MARKET_NEWS = Tool(
    name="get_market_news",
    description=(
        "Zwraca najnowsze ogólne wiadomości rynkowe (do 5): tytuł, skrót, wydawca, data "
        "publikacji i adres artykułu."
    ),
    input_model=MarketNewsInput,
    func=_get_market_news,
    group="market",
    uses_internet=True,
)

SEARCH_SYMBOL = Tool(
    name="search_symbol",
    description=(
        "Wyszukuje symbole giełdowe po nazwie spółki lub tickerze (do 5 trafień: symbol, "
        "nazwa, giełda, typ instrumentu)."
    ),
    input_model=SearchInput,
    func=_search_symbol,
    group="market",
    uses_internet=True,
)

GET_WIKIPEDIA_SUMMARY = Tool(
    name="get_wikipedia_summary",
    description="Zwraca krótkie streszczenie hasła z polskiej Wikipedii wraz z adresem artykułu.",
    input_model=SearchInput,
    func=_get_wikipedia_summary,
    group="market",
    uses_internet=True,
)

GET_INSTRUMENT_UNIVERSE = Tool(
    name="get_instrument_universe",
    description=(
        "Zwraca wbudowaną listę przykładowych instrumentów (nazwa, symbol, klasa aktywów, "
        "poziom ryzyka 1-5, opis, adres notowania), z których można wybierać propozycje."
    ),
    input_model=EmptyIn,
    func=_get_instrument_universe,
    group="market",
    uses_internet=False,
)
