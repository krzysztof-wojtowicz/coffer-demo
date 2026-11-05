from datetime import datetime

from pydantic import BaseModel


class QuoteOut(BaseModel):
    symbol: str
    name: str | None
    price: str
    currency: str
    change_pct: str | None
    as_of: datetime


class QuotesOut(BaseModel):
    quotes: list[QuoteOut]
