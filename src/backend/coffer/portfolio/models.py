import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from coffer.core.db import Base

ASSET_CLASSES = ("stock", "etf", "bond", "real_estate", "commodity", "crypto", "cash")


class Holding(Base):
    """One investment position entered by the user. Prices are per unit."""

    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    symbol: Mapped[str | None] = mapped_column(String(20))
    asset_class: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="PLN", server_default="PLN")
    purchase_date: Mapped[dt.date | None] = mapped_column(Date)
    manual_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
