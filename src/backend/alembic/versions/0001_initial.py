"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DEFAULT_CATEGORIES = [
    "Jedzenie",
    "Transport",
    "Mieszkanie",
    "Rachunki",
    "Zdrowie",
    "Rozrywka",
    "Zakupy",
    "Wynagrodzenie",
    "Inne",
]
NON_BUDGET_CATEGORIES = ["Przelewy własne", "Inwestycje"]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    categories = op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("in_budget", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="PLN"),
        sa.Column("base_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index("ix_transactions_user_id_date", "transactions", ["user_id", "date"])
    op.bulk_insert(
        categories,
        [{"name": n, "in_budget": True, "is_default": n == "Inne"} for n in DEFAULT_CATEGORIES]
        + [{"name": n, "in_budget": False, "is_default": False} for n in NON_BUDGET_CATEGORIES],
    )


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("categories")
    op.drop_table("auth_sessions")
    op.drop_table("users")
