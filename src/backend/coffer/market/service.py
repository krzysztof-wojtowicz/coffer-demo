"""Market data from public financial sources (Yahoo Finance via `yfinance`).

Core module: no LLM, no database. Results are cached in memory for ~5 minutes.
"""

import math
import re
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Literal

import httpx

from coffer.core.money import quantize

CACHE_TTL_S = 300.0
NEWS_SYMBOLS = ("SPY", "VT", "BND", "GLD")
SUMMARY_MAX_LEN = 400

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
_fx_cache: dict[tuple[str, str], tuple[float, Decimal | None]] = {}

FX_PLACES = Decimal("0.000001")


class _UnknownSymbol(Exception):
    pass


def clear_cache() -> None:
    with _lock:
        _quote_cache.clear()
        _tips_cache.clear()
        _fx_cache.clear()
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
        info = yf.Ticker(symbol).fast_info
        last = _to_decimal(info["lastPrice"])
        prev = _to_decimal(info["previousClose"])
        currency = info["currency"]
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


def get_quotes(symbols: list[str]) -> dict[str, Quote]:
    """Current quotes keyed by (upper-cased) symbol.

    Unknown symbols are skipped. Raises MarketDataUnavailable when the source cannot be
    reached and no quote could be returned.
    """
    now = time.monotonic()
    result: dict[str, Quote] = {}
    network_error: Exception | None = None
    for sym in _normalize_symbols(symbols):
        with _lock:
            cached = _quote_cache.get(sym)
        if cached is not None and now - cached[0] < CACHE_TTL_S:
            if cached[1] is not None:
                result[sym] = cached[1]
            continue
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
    if network_error is not None and not result:
        raise MarketDataUnavailable(str(network_error)) from network_error
    return result


def _fetch_fx_rate(pair: str) -> Decimal | None:
    """Last price of a Yahoo FX pair (e.g. USDPLN=X). Errors propagate."""
    import yfinance as yf

    return _to_decimal(yf.Ticker(pair).fast_info["lastPrice"])


def get_fx_rate(from_ccy: str, to_ccy: str) -> Decimal | None:
    """Exchange rate from_ccy -> to_ccy with 6 decimal places (half-up).

    Same currency gives Decimal("1") without network. Unknown pair or any error gives None;
    never raises. Successful lookups (and unknown pairs) are cached for CACHE_TTL_S.
    """
    src, dst = from_ccy.strip().upper(), to_ccy.strip().upper()
    if not src.isalpha() or not dst.isalpha():  # also keeps the pair a safe ticker
        return None
    if src == dst:
        return Decimal("1")
    key = (src, dst)
    now = time.monotonic()
    with _lock:
        cached = _fx_cache.get(key)
    if cached is not None and now - cached[0] < CACHE_TTL_S:
        return cached[1]
    try:
        raw = _fetch_fx_rate(f"{src}{dst}=X")
    except Exception as exc:
        if not _is_unknown_symbol_error(exc) or not _source_reachable():
            return None  # network problem: do not cache
        raw = None
    if raw is None and not _source_reachable():
        return None
    rate = raw.quantize(FX_PLACES, rounding=ROUND_HALF_UP) if raw is not None and raw > 0 else None
    with _lock:
        _fx_cache[key] = (now, rate)
    return rate


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
    title = (content.get("title") or "").strip()
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
        title=title, summary=summary, source=str(source), url=url, published_at=published
    )


def _fetch_news(symbol: str, count: int) -> list[dict[str, Any]]:
    import yfinance as yf

    return list(yf.Ticker(symbol).get_news(count=count) or [])


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
