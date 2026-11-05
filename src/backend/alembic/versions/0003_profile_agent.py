"""investment profile, agent runs, suggestions

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _user_fk() -> sa.Column:
    return sa.Column(
        "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


def _created() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "investment_profiles",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("horizon", sa.String(10), nullable=False),
        sa.Column("risk", sa.String(10), nullable=False),
        sa.Column("preferred_classes", JSONB(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        _user_fk(),
        sa.Column("task", sa.String(30), nullable=False),
        sa.Column("prompt_version", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("tool_calls", JSONB(), nullable=False, server_default="[]"),
        sa.Column("messages", JSONB(), nullable=False, server_default="[]"),
        sa.Column("raw_outputs", JSONB(), nullable=False, server_default="[]"),
        sa.Column("validation_errors", JSONB(), nullable=False, server_default="[]"),
        sa.Column("error", sa.Text()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("duration_ms", sa.Integer()),
        _created(),
    )
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index("ix_agent_runs_created_at", "agent_runs", ["created_at"])
    op.create_table(
        "suggestions",
        sa.Column("id", sa.Integer(), primary_key=True),
        _user_fk(),
        sa.Column(
            "agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id", ondelete="SET NULL")
        ),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("month", sa.String(7)),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("rationale", JSONB(), nullable=False),
        sa.Column("risks", JSONB(), nullable=False, server_default="[]"),
        sa.Column("sources", JSONB(), nullable=False, server_default="[]"),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("profile_snapshot", JSONB()),
        sa.Column("data_snapshot", JSONB(), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        _created(),
    )
    op.create_index("ix_suggestions_user_id", "suggestions", ["user_id"])
    op.create_index("ix_suggestions_created_at", "suggestions", ["created_at"])


def downgrade() -> None:
    op.drop_table("suggestions")
    op.drop_table("agent_runs")
    op.drop_table("investment_profiles")
