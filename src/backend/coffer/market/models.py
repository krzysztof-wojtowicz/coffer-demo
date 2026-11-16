import datetime as dt
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Numeric, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from coffer.core.db import Base


class MarketQuote(Base):
    """One persisted quote per symbol and day. Global table: no user data."""

    __tablename__ = "market_quotes"
    __table_args__ = (
        PrimaryKeyConstraint("symbol", "quote_date", name="pk_market_quotes"),
        CheckConstraint("price > 0", name="ck_market_quotes_price"),
    )

    symbol: Mapped[str] = mapped_column(String(20))
    quote_date: Mapped[dt.date] = mapped_column(Date)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    currency: Mapped[str] = mapped_column(String(3))
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(9, 4))
    source: Mapped[str] = mapped_column(String(20), default="yahoo", server_default="yahoo")
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
