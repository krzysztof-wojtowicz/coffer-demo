"""display names, shared asset classes, drop budget limits

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-27
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

UP: dict[str, str | None] = {"stocks": "stock", "bonds": "bond", "deposit": "cash"}
# commodity has no old equivalent and deposit cannot be restored (it was merged into cash).
DOWN: dict[str, str | None] = {"stock": "stocks", "bond": "bonds", "commodity": None}


def map_classes(
    classes: list[str], mapping: dict[str, str | None], fallback: list[str] | None = None
) -> list[str]:
    """Rename classes, dropping those mapped to None and removing duplicates (order kept)."""
    renamed = (mapping.get(c, c) for c in classes)
    return list(dict.fromkeys(c for c in renamed if c is not None)) or fallback or []


def _remap(mapping: dict[str, str | None], fallback: list[str] | None = None) -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT user_id, preferred_classes FROM investment_profiles"))
    for user_id, classes in rows.all():
        conn.execute(
            sa.text(
                "UPDATE investment_profiles SET preferred_classes = CAST(:c AS jsonb) "
                "WHERE user_id = :u"
            ),
            {"c": json.dumps(map_classes(classes, mapping, fallback)), "u": user_id},
        )


def upgrade() -> None:
    # Existing accounts have no name; every user table cascades from users, so this wipes all data.
    op.execute("DELETE FROM users")
    op.add_column("users", sa.Column("display_name", sa.String(50), nullable=False))
    _remap(UP)  # defensive only: the deleted users took their profiles with them
    op.drop_table("budget_limits")


def downgrade() -> None:
    op.create_table(
        "budget_limits",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("user_id", "category_id", name="pk_budget_limits"),
        sa.CheckConstraint("amount > 0", name="ck_budget_limits_amount"),
    )
    _remap(DOWN, ["deposit"])  # the old app requires at least one class
    op.drop_column("users", "display_name")
