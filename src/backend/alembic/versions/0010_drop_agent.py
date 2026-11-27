"""drop the AI assistant tables (agent_runs, suggestions, llm_usage_daily)

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

RUN_STATUSES = "('ok','invalid','unavailable','limited','timeout','no_data','error','no_surplus')"
PROVIDERS = "('ollama','openai','gemini','anthropic')"


def upgrade() -> None:
    # suggestions references agent_runs, so it goes first.
    op.drop_table("suggestions")
    op.drop_table("agent_runs")
    op.drop_table("llm_usage_daily")


def downgrade() -> None:
    # Tables as they stood after 0007; the dropped rows are not restored.
    user_fk = lambda: sa.Column(  # noqa: E731
        "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created = lambda: sa.Column(  # noqa: E731
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    op.create_table(
        "llm_usage_daily",
        user_fk(),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("user_id", "day", name="pk_llm_usage_daily"),
        sa.CheckConstraint("runs >= 0", name="ck_llm_usage_daily_runs"),
        sa.CheckConstraint("input_tokens >= 0", name="ck_llm_usage_daily_input_tokens"),
        sa.CheckConstraint("output_tokens >= 0", name="ck_llm_usage_daily_output_tokens"),
    )
    op.create_index("ix_llm_usage_daily_day", "llm_usage_daily", ["day"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        user_fk(),
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
        created(),
        sa.Column("provider", sa.String(20)),
        sa.Column("params", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("steps", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("llm_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6)),
        sa.CheckConstraint(
            f"provider IS NULL OR provider IN {PROVIDERS}", name="ck_agent_runs_provider"
        ),
        sa.CheckConstraint("llm_calls >= 0", name="ck_agent_runs_llm_calls"),
        sa.CheckConstraint("cost_usd IS NULL OR cost_usd >= 0", name="ck_agent_runs_cost_usd"),
        sa.CheckConstraint(f"status IN {RUN_STATUSES}", name="ck_agent_runs_status"),
    )
    op.create_index("ix_agent_runs_user_id_created_at", "agent_runs", ["user_id", "created_at"])

    op.create_table(
        "suggestions",
        sa.Column("id", sa.Integer(), primary_key=True),
        user_fk(),
        sa.Column(
            "agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id", ondelete="SET NULL")
        ),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("month", sa.String(7)),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("rationale", JSONB()),
        sa.Column("risks", JSONB(), nullable=False, server_default="[]"),
        sa.Column("sources", JSONB(), nullable=False, server_default="[]"),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("profile_snapshot", JSONB()),
        sa.Column("data_snapshot", JSONB(), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        created(),
        sa.Column("source", sa.String(10), nullable=False, server_default="ai"),
        sa.Column("ai_status", sa.String(20), nullable=False, server_default="ok"),
        sa.Column("params", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("provider", sa.String(20)),
        sa.Column("report", JSONB(), nullable=False),
        sa.CheckConstraint("source IN ('ai','rules')", name="ck_suggestions_source"),
        sa.CheckConstraint(
            f"provider IS NULL OR provider IN {PROVIDERS}", name="ck_suggestions_provider"
        ),
    )
    op.create_index("ix_suggestions_user_id_created_at", "suggestions", ["user_id", "created_at"])
