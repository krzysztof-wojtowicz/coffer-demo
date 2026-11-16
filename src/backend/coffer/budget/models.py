import datetime as dt
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, PrimaryKeyConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from coffer.core.db import Base


class BudgetLimit(Base):
    """Monthly spending limit for one in-budget category (F12/F13)."""

    __tablename__ = "budget_limits"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "category_id", name="pk_budget_limits"),
        CheckConstraint("amount > 0", name="ck_budget_limits_amount"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
