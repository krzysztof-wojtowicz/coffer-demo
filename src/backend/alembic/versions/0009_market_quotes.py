"""persistent market quotes (global, no user data)

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-16
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_quotes",
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("quote_date", sa.Date(), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("change_pct", sa.Numeric(9, 4)),
        sa.Column("source", sa.String(20), nullable=False, server_default="yahoo"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "quote_date", name="pk_market_quotes"),
        sa.CheckConstraint("price > 0", name="ck_market_quotes_price"),
    )


def downgrade() -> None:
    op.drop_table("market_quotes")
