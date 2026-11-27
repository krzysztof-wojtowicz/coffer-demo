"""Quotes and FX rates from Yahoo Finance via `yfinance`; no API keys. Two cache layers:
1. in memory (process-local, ~5 minutes);
2. optionally the `market_quotes` table (one persisted quote per symbol and day), used only
   when the caller passes a `db` session.
`get_quotes` raises `MarketDataUnavailable` when nothing could be served.
"""

import logging
import math
import re
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

import httpx

from coffer.core.money import quantize

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

CACHE_TTL_S = 300.0


class MarketDataUnavailable(Exception):
    """The market data source could not be reached."""


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: Decimal
    currency: str
    change_pct: Decimal | None
    as_of: datetime


_lock = threading.Lock()
_quote_cache: dict[str, tuple[float, Quote | None]] = {}
_fx_cache: dict[tuple[str, str], tuple[float, Decimal | None, datetime]] = {}
HTTP_TIMEOUT_S = 10.0

FX_PLACES = Decimal("0.000001")


class _UnknownSymbol(Exception):
    pass


def clear_cache() -> None:
    with _lock:
        _quote_cache.clear()
        _fx_cache.clear()
        _probe_ok_at.clear()


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
        _upsert_quotes(db, [Quote(pair, rate, dst, None, fetched)])
    return rate, fetched


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
