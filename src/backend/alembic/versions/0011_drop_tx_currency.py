"""drop transactions.currency and transactions.base_amount (PLN only, base == amount)

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("transactions", "base_amount")
    op.drop_column("transactions", "currency")


def downgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("currency", sa.String(3), nullable=False, server_default="PLN"),
    )
    op.add_column("transactions", sa.Column("base_amount", sa.Numeric(14, 2), nullable=True))
    op.execute("UPDATE transactions SET base_amount = amount")
    op.alter_column("transactions", "base_amount", nullable=False)
