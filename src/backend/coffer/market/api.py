from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from coffer.accounts.deps import CurrentUser
from coffer.market import service
from coffer.market.schemas import QuoteOut, QuotesOut

router = APIRouter(prefix="/api/market", tags=["market"])

MAX_SYMBOLS = 50


@router.get("/quotes", response_model=QuotesOut)
def quotes(
    user: CurrentUser,
    symbols: Annotated[str, Query(description="Symbole oddzielone przecinkami, np. AAPL,MSFT")],
) -> QuotesOut:
    requested = [s for s in symbols.split(",") if s.strip()][:MAX_SYMBOLS]
    try:
        found = service.get_quotes(requested)
    except service.MarketDataUnavailable as exc:
        raise HTTPException(
            503, "Dane rynkowe są chwilowo niedostępne. Spróbuj ponownie później."
        ) from exc
    return QuotesOut(quotes=[quote_out(q) for q in found.values()])


def quote_out(q: service.Quote) -> QuoteOut:
    return QuoteOut(
        symbol=q.symbol,
        name=q.name,
        price=str(q.price),
        currency=q.currency,
        change_pct=None if q.change_pct is None else str(q.change_pct),
        as_of=q.as_of,
    )
