import datetime as dt

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from coffer.core.db import Base

HORIZONS = ("short", "medium", "long")
RISK_LEVELS = ("low", "medium", "high")
ASSET_CLASSES = ("cash", "deposit", "stocks", "etf", "bonds", "crypto", "real_estate")


class InvestmentProfile(Base):
    """One profile per user (UC-05). Values are the enum codes above."""

    __tablename__ = "investment_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    horizon: Mapped[str] = mapped_column(String(10))
    risk: Mapped[str] = mapped_column(String(10))
    preferred_classes: Mapped[list[str]] = mapped_column(JSONB)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
