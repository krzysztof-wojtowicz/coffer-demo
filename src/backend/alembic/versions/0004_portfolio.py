"""portfolio holdings

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("symbol", sa.String(20)),
        sa.Column("asset_class", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("purchase_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="PLN"),
        sa.Column("purchase_date", sa.Date()),
        sa.Column("manual_value", sa.Numeric(14, 2)),
        sa.Column("note", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "asset_class IN ('stock','etf','bond','real_estate','commodity','crypto','cash')",
            name="ck_holdings_asset_class",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_holdings_quantity_positive"),
    )
    op.create_index("ix_holdings_user_id", "holdings", ["user_id"])


def downgrade() -> None:
    op.drop_table("holdings")
