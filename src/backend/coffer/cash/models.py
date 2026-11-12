import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from coffer.core.db import Base


class OpeningBalance(Base):
    """One opening balance per user: the cash amount as of `as_of` (inclusive)."""

    __tablename__ = "opening_balances"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    as_of: Mapped[dt.date] = mapped_column(Date)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
