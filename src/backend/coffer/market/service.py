"""Market data from public financial sources (Yahoo Finance via `yfinance`, Wikipedia REST).

Core module, no LLM, no API keys. Two cache layers:
1. in memory (process-local, ~5 minutes for quotes, 1 h for history, 6 h for profiles);
2. optionally the `market_quotes` table (one persisted quote per symbol and day), used only
   when the caller passes a `db` session. Without `db` (MCP server) nothing touches a database.
Functions reaching the Internet never raise on source errors: they return None or an empty
list (exception: `get_quotes` raises `MarketDataUnavailable` when nothing could be served).
"""

import logging
import math
import re
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import quote as url_quote

import httpx

from coffer.core.money import quantize

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

CACHE_TTL_S = 300.0
NEWS_SYMBOLS = ("SPY", "VT", "BND", "GLD")
SUMMARY_MAX_LEN = 400
TITLE_MAX_LEN = 200
SOURCE_MAX_LEN = 100

AssetClass = Literal["stock", "etf", "bond", "real_estate", "commodity", "crypto", "cash"]
ASSET_CLASSES: tuple[str, ...] = (
    "stock",
    "etf",
    "bond",
    "real_estate",
    "commodity",
    "crypto",
    "cash",
)


class MarketDataUnavailable(Exception):
    """The market data source could not be reached."""


@dataclass(frozen=True)
class Quote:
    symbol: str
    name: str | None
    price: Decimal
    currency: str
    change_pct: Decimal | None
    as_of: datetime


@dataclass(frozen=True)
class MarketTip:
    title: str
    summary: str
    source: str
    url: str | None
    published_at: datetime | None
    fetched_at: datetime | None = None


@dataclass(frozen=True)
class RefreshReport:
    updated: int
    failed: list[str]


@dataclass(frozen=True)
class PriceHistory:
    symbol: str
    currency: str | None
    points: list[tuple[date, Decimal]]
    fetched_at: datetime
    source_url: str


@dataclass(frozen=True)
class CompanyProfile:
    symbol: str
    name: str | None
    sector: str | None
    industry: str | None
    country: str | None
    website: str | None
    summary: str | None
    market_cap: Decimal | None
    pe_ratio: Decimal | None
    dividend_yield: Decimal | None
    currency: str | None
    fetched_at: datetime
    source_url: str


@dataclass(frozen=True)
class SymbolMatch:
    symbol: str
    name: str | None
    exchange: str | None
    type: str | None


@dataclass(frozen=True)
class EncyclopediaEntry:
    title: str
    extract: str
    url: str
    fetched_at: datetime


@dataclass(frozen=True)
class Instrument:
    name: str
    symbol: str | None
    asset_class: AssetClass
    risk_level: int  # 1 (lowest) .. 5 (highest)
    description: str


_UNIVERSE: tuple[Instrument, ...] = (
    Instrument(
        "Lokata bankowa / konto oszczędnościowe",
        None,
        "cash",
        1,
        "Gwarantowany depozyt, pełna płynność lub krótki termin, niska stopa zwrotu.",
    ),
    Instrument(
        "Obligacje skarbowe indeksowane inflacją (EDO/COI)",
        None,
        "bond",
        1,
        "Detaliczne obligacje Skarbu Państwa chroniące przed inflacją.",
    ),
    Instrument(
        "Vanguard Total Bond Market ETF",
        "BND",
        "bond",
        2,
        "Szeroki koszyk amerykańskich obligacji o ratingu inwestycyjnym.",
    ),
    Instrument(
        "iShares TIPS Bond ETF",
        "TIP",
        "bond",
        2,
        "Amerykańskie obligacje skarbowe indeksowane inflacją.",
    ),
    Instrument(
        "Vanguard Total World Stock ETF",
        "VT",
        "etf",
        3,
        "Globalny ETF akcyjny, tysiące spółek z rynków rozwiniętych i wschodzących.",
    ),
    Instrument(
        "SPDR S&P 500 ETF",
        "SPY",
        "etf",
        3,
        "500 największych spółek z USA w jednym funduszu.",
    ),
    Instrument(
        "Vanguard Real Estate ETF",
        "VNQ",
        "real_estate",
        3,
        "Fundusze REIT z rynku nieruchomości komercyjnych i mieszkaniowych w USA.",
    ),
    Instrument(
        "SPDR Gold Shares",
        "GLD",
        "commodity",
        3,
        "ETF odwzorowujący cenę złota, zabezpieczenie przed inflacją i kryzysami.",
    ),
    Instrument(
        "Apple Inc.",
        "AAPL",
        "stock",
        4,
        "Pojedyncza spółka technologiczna o dużej kapitalizacji.",
    ),
    Instrument(
        "Microsoft Corp.",
        "MSFT",
        "stock",
        4,
        "Pojedyncza spółka technologiczna (oprogramowanie, chmura).",
    ),
    Instrument(
        "PKO Bank Polski",
        "PKO.WA",
        "stock",
        4,
        "Największy bank notowany na GPW.",
    ),
    Instrument(
        "Bitcoin",
        "BTC-USD",
        "crypto",
        5,
        "Kryptowaluta o bardzo wysokiej zmienności.",
    ),
)

_NAMES = {i.symbol: i.name for i in _UNIVERSE if i.symbol}

_lock = threading.Lock()
_quote_cache: dict[str, tuple[float, Quote | None]] = {}
_tips_cache: dict[int, tuple[float, list[MarketTip]]] = {}
_fx_cache: dict[tuple[str, str], tuple[float, Decimal | None, datetime]] = {}
_history_cache: dict[tuple[str, str], tuple[float, PriceHistory | None]] = {}
_profile_cache: dict[str, tuple[float, CompanyProfile | None]] = {}
HISTORY_TTL_S = 3600.0
PROFILE_TTL_S = 6 * 3600.0
HTTP_TIMEOUT_S = 10.0

FX_PLACES = Decimal("0.000001")


class _UnknownSymbol(Exception):
    pass


def clear_cache() -> None:
    with _lock:
        _quote_cache.clear()
        _tips_cache.clear()
        _fx_cache.clear()
        _history_cache.clear()
        _profile_cache.clear()
        _probe_ok_at.clear()


def get_instrument_universe() -> list[Instrument]:
    return list(_UNIVERSE)


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    try:
        return Decimal(str(f))
    except InvalidOperation:
        return None


def _is_unknown_symbol_error(exc: Exception) -> bool:
    """yfinance raises lookup-style errors for unknown tickers; anything else is the network.

    Note: without network yfinance may also end in a KeyError, so callers confirm an
    "unknown" verdict with `_source_reachable()` before trusting (and caching) it.
    """
    if isinstance(exc, OSError):  # requests / curl_cffi / socket errors
        return False
    if isinstance(exc, KeyError | ValueError | TypeError | IndexError | AttributeError):
        return True
    try:
        from yfinance.exceptions import YFException, YFRateLimitError
    except ImportError:  # pragma: no cover
        return False
    return isinstance(exc, YFException) and not isinstance(exc, YFRateLimitError)


PROBE_URL = "https://query1.finance.yahoo.com/"
PROBE_TTL_S = 30.0
_probe_ok_at: list[float] = []


def _source_reachable() -> bool:
    """Cheap connectivity check of Yahoo Finance (any HTTP response counts as reachable)."""
    now = time.monotonic()
    with _lock:
        if _probe_ok_at and now - _probe_ok_at[0] < PROBE_TTL_S:
            return True
    try:
        httpx.get(PROBE_URL, timeout=3.0)
    except httpx.HTTPError:
        return False
    with _lock:
        _probe_ok_at[:] = [now]
    return True


def _fetch_quote(symbol: str) -> Quote:
    """Fetch one quote. Raises _UnknownSymbol for missing tickers, other errors for network."""
    import yfinance as yf

    try:

        def read() -> tuple[Any, Any, Any]:
            info = yf.Ticker(symbol).fast_info
            return info["lastPrice"], info["previousClose"], info["currency"]

        raw_last, raw_prev, currency = _with_timeout(read)
        last = _to_decimal(raw_last)
        prev = _to_decimal(raw_prev)
    except Exception as exc:
        if _is_unknown_symbol_error(exc):
            raise _UnknownSymbol(symbol) from exc
        raise
    if last is None or not currency:
        raise _UnknownSymbol(symbol)
    change = quantize((last - prev) * 100 / prev) if prev else None
    return Quote(
        symbol=symbol,
        name=_NAMES.get(symbol),
        price=quantize(last),
        currency=str(currency).upper(),
        change_pct=change,
        as_of=datetime.now(UTC),
    )


# Yahoo tickers (AAPL, PKO.WA, BTC-USD, ^GSPC, USDPLN=X). yfinance puts the symbol into the
# request URL path, so anything else (/, ?, #, spaces, long input) is rejected.
_SYMBOL_RE = re.compile(r"[A-Z0-9^][A-Z0-9.=^-]{0,19}")


def normalize_symbol(symbol: str) -> str | None:
    """Upper-cased Yahoo ticker, or None when it is not a plausible ticker."""
    sym = symbol.strip().upper()
    return sym if _SYMBOL_RE.fullmatch(sym) else None


def _normalize_symbols(symbols: list[str]) -> list[str]:
    out: list[str] = []
    for s in symbols:
        sym = normalize_symbol(s)
        if sym and sym not in out:
            out.append(sym)
    return out


def _today() -> date:
    return datetime.now(UTC).date()


DB_QUOTE_MAX_AGE = timedelta(hours=6)


def _db_quotes(
    db: "Session", symbols: list[str], max_age: timedelta | None = DB_QUOTE_MAX_AGE
) -> dict[str, Quote]:
    """Today's persisted quotes, optionally only those fetched within `max_age`.

    Errors degrade to an empty result.
    """
    from sqlalchemy import select

    from coffer.market.models import MarketQuote

    if not symbols:
        return {}
    stmt = select(MarketQuote).where(
        MarketQuote.symbol.in_(symbols), MarketQuote.quote_date == _today()
    )
    if max_age is not None:
        stmt = stmt.where(MarketQuote.fetched_at >= datetime.now(UTC) - max_age)
    try:
        with db.begin_nested():  # SAVEPOINT: a failure must not poison the caller's transaction
            rows = db.scalars(stmt).all()
    except Exception:
        log.warning("market_quotes read failed", exc_info=True)
        return {}
    return {
        r.symbol: Quote(
            symbol=r.symbol,
            name=_NAMES.get(r.symbol),
            price=r.price,
            currency=r.currency,
            change_pct=r.change_pct,
            as_of=r.fetched_at,
        )
        for r in rows
    }


def _upsert_quotes(db: "Session", quotes: Sequence[Quote]) -> None:
    """UPSERT one row per (symbol, day) inside a SAVEPOINT; the caller commits.

    Errors are logged and swallowed (the caller's transaction stays usable).
    """
    from sqlalchemy.dialects.postgresql import insert

    from coffer.market.models import MarketQuote

    if not quotes:
        return
    try:
        with db.begin_nested():
            for q in quotes:
                values = {
                    "symbol": q.symbol,
                    "quote_date": q.as_of.astimezone(UTC).date(),
                    "price": q.price,
                    "currency": q.currency[:3],
                    "change_pct": q.change_pct,
                    "source": "yahoo",
                    "fetched_at": q.as_of,
                }
                stmt = insert(MarketQuote).values(**values)
                db.execute(
                    stmt.on_conflict_do_update(
                        constraint="pk_market_quotes",
                        set_={k: v for k, v in values.items() if k not in ("symbol", "quote_date")},
                    )
                )
    except Exception:
        log.warning("market_quotes write failed", exc_info=True)


def get_quotes(symbols: list[str], db: "Session | None" = None) -> dict[str, Quote]:
    """Current quotes keyed by (upper-cased) symbol: memory, then today's `market_quotes`
    row (only with `db`), then the source (persisted when `db` is given).

    Unknown symbols are skipped. Raises MarketDataUnavailable when the source cannot be
    reached and no quote could be returned.
    """
    now = time.monotonic()
    result: dict[str, Quote] = {}
    pending: list[str] = []
    for sym in _normalize_symbols(symbols):
        with _lock:
            cached = _quote_cache.get(sym)
        if cached is not None and now - cached[0] < CACHE_TTL_S:
            if cached[1] is not None:
                result[sym] = cached[1]
            continue
        pending.append(sym)
    if db is not None:
        stored = _db_quotes(db, pending)
        with _lock:
            for sym, q in stored.items():
                _quote_cache[sym] = (now, q)
        result.update(stored)
        pending = [s for s in pending if s not in stored]
    network_error: Exception | None = None
    fresh: list[Quote] = []
    for sym in pending:
        if network_error is not None:  # source is down: serve only from cache
            continue
        try:
            quote: Quote | None = _fetch_quote(sym)
        except _UnknownSymbol:
            if not _source_reachable():  # offline yfinance looks like "unknown symbol"
                network_error = MarketDataUnavailable("Źródło danych rynkowych nieosiągalne")
                continue
            quote = None
        except Exception as exc:
            network_error = exc
            continue
        with _lock:
            _quote_cache[sym] = (now, quote)
        if quote is not None:
            result[sym] = quote
            fresh.append(quote)
    if db is not None:
        _upsert_quotes(db, fresh)
    if network_error is not None and not result:
        raise MarketDataUnavailable(str(network_error)) from network_error
    return result


def stored_quotes(
    db: "Session", symbols: list[str], max_age: timedelta | None = None
) -> dict[str, Quote]:
    """Today's persisted quotes for `symbols`, newer than `max_age` when given (no network)."""
    return _db_quotes(db, _normalize_symbols(symbols), max_age)


@dataclass(frozen=True)
class FetchResult:
    quotes: list[Quote]
    failed: list[str]


def fetch_quotes(symbols: list[str]) -> FetchResult:
    """Force-fetch quotes from the source (network only: no database). Never raises."""
    now = time.monotonic()
    fresh: list[Quote] = []
    failed: list[str] = []
    for sym in _normalize_symbols(symbols):
        try:
            quote = _fetch_quote(sym)
        except Exception:
            failed.append(sym)
            continue
        with _lock:
            _quote_cache[sym] = (now, quote)
        fresh.append(quote)
    return FetchResult(fresh, failed)


def store_quotes(db: "Session", quotes: Sequence[Quote]) -> None:
    """UPSERT quotes for their day (SAVEPOINT; the caller commits)."""
    _upsert_quotes(db, quotes)


def refresh_quotes(db: "Session", symbols: list[str]) -> RefreshReport:
    """fetch_quotes + store_quotes in one call (caller commits). Never raises."""
    result = fetch_quotes(symbols)
    store_quotes(db, result.quotes)
    return RefreshReport(updated=len(result.quotes), failed=result.failed)


def _fetch_fx_rate(pair: str) -> Decimal | None:
    """Last price of a Yahoo FX pair (e.g. USDPLN=X). Errors propagate."""
    import yfinance as yf

    return _to_decimal(_with_timeout(lambda: yf.Ticker(pair).fast_info["lastPrice"]))


def get_fx_quote(
    from_ccy: str, to_ccy: str, db: "Session | None" = None
) -> tuple[Decimal, datetime] | None:
    """Exchange rate from_ccy -> to_ccy (6 decimal places, half-up) with its timestamp.

    Same currency gives (1, now) without network. Unknown pair or any error gives None;
    never raises. Order: memory, today's `market_quotes` row (with `db`), source.
    """
    src, dst = from_ccy.strip().upper(), to_ccy.strip().upper()
    if not src.isalpha() or not dst.isalpha():  # also keeps the pair a safe ticker
        return None
    if src == dst:
        return Decimal("1"), datetime.now(UTC)
    key = (src, dst)
    pair = f"{src}{dst}=X"
    now = time.monotonic()
    with _lock:
        cached = _fx_cache.get(key)
    if cached is not None and now - cached[0] < CACHE_TTL_S:
        return None if cached[1] is None else (cached[1], cached[2])
    if db is not None:
        stored = _db_quotes(db, [pair]).get(pair)
        if stored is not None:
            stored_rate = stored.price.quantize(FX_PLACES, rounding=ROUND_HALF_UP)
            with _lock:
                _fx_cache[key] = (now, stored_rate, stored.as_of)
            return stored_rate, stored.as_of
    try:
        raw = _fetch_fx_rate(pair)
    except Exception as exc:
        if not _is_unknown_symbol_error(exc) or not _source_reachable():
            return None  # network problem: do not cache
        raw = None
    if raw is None and not _source_reachable():
        return None
    rate = raw.quantize(FX_PLACES, rounding=ROUND_HALF_UP) if raw is not None and raw > 0 else None
    fetched = datetime.now(UTC)
    with _lock:
        _fx_cache[key] = (now, rate, fetched)
    if rate is None:
        return None
    if db is not None:
        _upsert_quotes(db, [Quote(pair, None, rate, dst, None, fetched)])
    return rate, fetched


def get_fx_rate(from_ccy: str, to_ccy: str) -> Decimal | None:
    """Exchange rate from_ccy -> to_ccy with 6 decimal places (half-up); None when unknown.

    Same currency gives Decimal("1") without network. Never raises.
    """
    result = get_fx_quote(from_ccy, to_ccy)
    return None if result is None else result[0]


_TAG_RE = re.compile(r"<[^>]+>")


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        if isinstance(value, int | float):
            return datetime.fromtimestamp(value, UTC)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, OverflowError, OSError):
        return None


def _parse_news_item(item: dict[str, Any]) -> MarketTip | None:
    """Supports both the current (`content` envelope) and the legacy yfinance news format."""
    raw_content = item.get("content")
    content: dict[str, Any] = raw_content if isinstance(raw_content, dict) else item
    title = str(content.get("title") or "").strip()[:TITLE_MAX_LEN]
    if not title:
        return None
    summary = content.get("summary") or content.get("description") or ""
    summary = _TAG_RE.sub("", str(summary)).strip()[:SUMMARY_MAX_LEN]
    provider = content.get("provider")
    source = (
        (provider.get("displayName") if isinstance(provider, dict) else None)
        or content.get("publisher")
        or "Yahoo Finance"
    )
    url = None
    for key in ("canonicalUrl", "clickThroughUrl"):
        link = content.get(key)
        if isinstance(link, dict) and link.get("url"):
            url = link["url"]
            break
    url = url or content.get("link")
    if not (isinstance(url, str) and url.startswith(("https://", "http://"))):
        url = None  # rendered as a link in the UI: no javascript:/data: schemes
    published = _parse_datetime(content.get("pubDate") or content.get("providerPublishTime"))
    return MarketTip(
        title=title,
        summary=summary,
        source=str(source)[:SOURCE_MAX_LEN],
        url=url,
        published_at=published,
    )


def _fetch_news(symbol: str, count: int) -> list[dict[str, Any]]:
    import yfinance as yf

    return _with_timeout(lambda: list(yf.Ticker(symbol).get_news(count=count) or []))


def get_market_tips(limit: int = 5) -> list[MarketTip]:
    """Recent market news for broad index/bond/gold ETFs. Empty list on any error."""
    limit = max(1, min(limit, 20))
    now = time.monotonic()
    with _lock:
        cached = _tips_cache.get(limit)
    if cached is not None and now - cached[0] < CACHE_TTL_S:
        return list(cached[1])
    tips: list[MarketTip] = []
    seen: set[str] = set()
    try:
        for sym in NEWS_SYMBOLS:
            for raw in _fetch_news(sym, limit):
                tip = _parse_news_item(raw) if isinstance(raw, dict) else None
                if tip is None or tip.title in seen:
                    continue
                seen.add(tip.title)
                tips.append(tip)
            if len(tips) >= limit:
                break
    except Exception:
        return []
    tips.sort(key=_published_key, reverse=True)
    tips = tips[:limit]
    with _lock:
        _tips_cache[limit] = (now, tips)
    return list(tips)


def _published_key(tip: MarketTip) -> datetime:
    return tip.published_at or datetime.min.replace(tzinfo=UTC)


# --- history, profile, company news, symbol search, Wikipedia -------------------------

MAX_HISTORY_POINTS = 260
PROFILE_SUMMARY_MAX_LEN = 1000
WIKI_EXTRACT_MAX_LEN = 1500
HistoryPeriod = Literal["1mo", "3mo", "6mo", "1y", "5y"]
HISTORY_PERIODS: tuple[str, ...] = ("1mo", "3mo", "6mo", "1y", "5y")
WIKI_USER_AGENT = "Mozilla/5.0 (compatible; personal-finance-app)"


def _downsample(points: list[tuple[date, Decimal]], limit: int) -> list[tuple[date, Decimal]]:
    """At most `limit` points, evenly spaced, always keeping the first and the last."""
    if len(points) <= limit:
        return points
    step = (len(points) - 1) / (limit - 1)
    return [points[round(i * step)] for i in range(limit)]


def _with_timeout[T](func: Callable[[], T], timeout: float = HTTP_TIMEOUT_S) -> T:
    """Run a blocking yfinance call in a worker thread; TimeoutError after `timeout` seconds.

    The worker is abandoned (daemon thread) when it overruns, so callers are never blocked.
    """
    box: list[Any] = []
    error: list[BaseException] = []

    def run() -> None:
        try:
            box.append(func())
        except BaseException as exc:  # re-raised in the caller's thread
            error.append(exc)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise TimeoutError("Źródło danych rynkowych nie odpowiedziało na czas")
    if error:
        raise error[0]
    return box[0]


def _fetch_history(symbol: str, period: str) -> Any:
    import yfinance as yf

    return _with_timeout(lambda: yf.Ticker(symbol).history(period=period, interval="1d"))


def _fetch_currency(symbol: str) -> str | None:
    import yfinance as yf

    try:
        value = _with_timeout(lambda: yf.Ticker(symbol).fast_info["currency"])
    except Exception:
        return None
    return str(value).upper() if value else None


def get_price_history(symbol: str, period: HistoryPeriod = "1y") -> PriceHistory | None:
    """Daily closing prices (max 260 points), cached for 1 h. None on any error."""
    sym = normalize_symbol(symbol)
    if sym is None or period not in HISTORY_PERIODS:
        return None
    key = (sym, period)
    now = time.monotonic()
    with _lock:
        cached = _history_cache.get(key)
    if cached is not None and now - cached[0] < HISTORY_TTL_S:
        return cached[1]
    try:
        frame = _fetch_history(sym, period)
        points: list[tuple[date, Decimal]] = []
        for index, value in frame["Close"].items():
            price = _to_decimal(value)
            if price is None or price <= 0:
                continue
            day = index.date() if hasattr(index, "date") else index
            points.append((day, quantize(price)))
        currency = _fetch_currency(sym)
    except Exception:
        log.warning("price history unavailable for %s", sym, exc_info=True)
        return None
    if not points:
        return None
    history = PriceHistory(
        symbol=sym,
        currency=currency,
        points=_downsample(points, MAX_HISTORY_POINTS),
        fetched_at=datetime.now(UTC),
        source_url=f"https://finance.yahoo.com/quote/{sym}/history",
    )
    with _lock:
        _history_cache[key] = (now, history)
    return history


def _fetch_info(symbol: str) -> dict[str, Any]:
    import yfinance as yf

    return _with_timeout(lambda: dict(yf.Ticker(symbol).info or {}))


def _text(value: Any, max_len: int | None = None) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    return text[:max_len] if max_len else text


def get_company_profile(symbol: str) -> CompanyProfile | None:
    """Company profile from Yahoo Finance, cached for 6 h. None on any error."""
    sym = normalize_symbol(symbol)
    if sym is None:
        return None
    now = time.monotonic()
    with _lock:
        cached = _profile_cache.get(sym)
    if cached is not None and now - cached[0] < PROFILE_TTL_S:
        return cached[1]
    try:
        info = _fetch_info(sym)
    except Exception:
        log.warning("company profile unavailable for %s", sym, exc_info=True)
        return None
    name = _text(info.get("longName")) or _text(info.get("shortName"))
    if not info or name is None:
        return None
    profile = CompanyProfile(
        symbol=sym,
        name=name,
        sector=_text(info.get("sector")),
        industry=_text(info.get("industry")),
        country=_text(info.get("country")),
        website=_text(info.get("website")),
        summary=_text(info.get("longBusinessSummary"), PROFILE_SUMMARY_MAX_LEN),
        market_cap=_to_decimal(info.get("marketCap")),
        pe_ratio=_to_decimal(info.get("trailingPE")),
        dividend_yield=_to_decimal(info.get("dividendYield")),
        currency=_text(info.get("currency")),
        fetched_at=datetime.now(UTC),
        source_url=f"https://finance.yahoo.com/quote/{sym}/profile",
    )
    with _lock:
        _profile_cache[sym] = (now, profile)
    return profile


def get_company_news(symbol: str, limit: int = 5) -> list[MarketTip]:
    """Recent news for one company (newest first, at most 10). Empty list on any error."""
    sym = normalize_symbol(symbol)
    if sym is None:
        return []
    limit = max(1, min(limit, 10))
    try:
        raw_items = _fetch_news(sym, limit)
    except Exception:
        log.warning("company news unavailable for %s", sym, exc_info=True)
        return []
    fetched = datetime.now(UTC)
    tips: list[MarketTip] = []
    seen: set[str] = set()
    for raw in raw_items:
        tip = _parse_news_item(raw) if isinstance(raw, dict) else None
        if tip is None or tip.title in seen:
            continue
        seen.add(tip.title)
        tips.append(replace(tip, fetched_at=fetched))
    tips.sort(key=_published_key, reverse=True)
    return tips[:limit]


def _search_yahoo(query: str, limit: int) -> list[dict[str, Any]]:
    import yfinance as yf

    return _with_timeout(lambda: list(yf.Search(query, max_results=limit).quotes or []))


def _universe_matches(query: str, limit: int) -> list[SymbolMatch]:
    needle = query.casefold()
    matches = [
        SymbolMatch(i.symbol, i.name, None, i.asset_class)
        for i in _UNIVERSE
        if i.symbol and (needle in i.symbol.casefold() or needle in i.name.casefold())
    ]
    return matches[:limit]


def search_symbols(query: str, limit: int = 5) -> list[SymbolMatch]:
    """Symbol search via Yahoo; falls back to the built-in instrument universe."""
    query = query.strip()[:50]
    if not query:
        return []
    limit = max(1, min(limit, 10))
    try:
        raw = _search_yahoo(query, limit)
    except Exception:
        log.warning("symbol search failed", exc_info=True)
        return _universe_matches(query, limit)
    matches: list[SymbolMatch] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        sym = normalize_symbol(str(item.get("symbol") or ""))
        if sym is None:
            continue
        matches.append(
            SymbolMatch(
                symbol=sym,
                name=_text(item.get("shortname")) or _text(item.get("longname")),
                exchange=_text(item.get("exchDisp")) or _text(item.get("exchange")),
                type=_text(item.get("quoteType")) or _text(item.get("typeDisp")),
            )
        )
    return matches[:limit] or _universe_matches(query, limit)


def _wiki_get(url: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    response = httpx.get(
        url,
        params=params,
        headers={"User-Agent": WIKI_USER_AGENT, "Accept": "application/json"},
        timeout=HTTP_TIMEOUT_S,
        follow_redirects=True,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else None


def get_wikipedia_summary(query: str, lang: str = "pl") -> EncyclopediaEntry | None:
    """Short encyclopedia summary from the Wikipedia REST API. None on any error."""
    query = query.strip()[:100]
    if not query or not re.fullmatch(r"[a-z]{2,3}", lang):
        return None
    base = f"https://{lang}.wikipedia.org"
    try:
        data = _wiki_get(f"{base}/api/rest_v1/page/summary/{url_quote(query, safe='')}")
        if data is None:  # not an exact title: take the best title match
            found = _wiki_get(f"{base}/w/rest.php/v1/search/title", {"q": query, "limit": 1})
            pages = (found or {}).get("pages") or []
            key = pages[0].get("key") if pages and isinstance(pages[0], dict) else None
            if not key:
                return None
            data = _wiki_get(f"{base}/api/rest_v1/page/summary/{url_quote(str(key), safe='')}")
        if data is None:
            return None
        extract = _text(data.get("extract"), WIKI_EXTRACT_MAX_LEN)
        title = _text(data.get("title"))
        urls = data.get("content_urls")
        page_url = urls.get("desktop", {}).get("page") if isinstance(urls, dict) else None
        if extract is None or title is None:
            return None
        if not (isinstance(page_url, str) and page_url.startswith(f"{base}/")):
            page_url = f"{base}/wiki/{url_quote(title.replace(' ', '_'), safe='')}"
    except Exception:
        log.warning("wikipedia lookup failed", exc_info=True)
        return None
    return EncyclopediaEntry(
        title=title, extract=extract, url=page_url, fetched_at=datetime.now(UTC)
    )
