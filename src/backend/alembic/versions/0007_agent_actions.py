"""agent actions: extended run trace, suggestion history, daily LLM usage

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

RUN_STATUSES = "('ok','invalid','unavailable','limited','timeout','no_data','error','no_surplus')"
PROVIDERS = "('ollama','openai','gemini','anthropic')"

# Converts the legacy suggestion layout (summary/rationale/risks/sources) to the report schema.
BACKFILL_REPORT = """
UPDATE suggestions SET report = jsonb_build_object(
    'headline', summary,
    'facts', '[]'::jsonb,
    'tables', '[]'::jsonb,
    'findings', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'title', r->>'claim',
            'detail', '',
            'refers_to', r->>'refers_to',
            'value', r->'value'
        ) ORDER BY ord)
        FROM jsonb_array_elements(
            CASE WHEN jsonb_typeof(rationale) = 'array' THEN rationale ELSE '[]'::jsonb END
        ) WITH ORDINALITY AS t(r, ord)
    ), '[]'::jsonb),
    'recommendations', '[]'::jsonb,
    'risks', COALESCE(risks, '[]'::jsonb),
    'sources', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'title', COALESCE(s->>'title', s->>'url'),
            'url', s->>'url',
            'publisher', s->'publisher',
            'published_at', s->'published_at',
            'fetched_at', to_jsonb(created_at)
        ) ORDER BY ord)
        FROM jsonb_array_elements(
            CASE WHEN jsonb_typeof(sources) = 'array' THEN sources ELSE '[]'::jsonb END
        ) WITH ORDINALITY AS t(s, ord)
        WHERE s->>'url' IS NOT NULL
    ), '[]'::jsonb),
    'disclaimer', disclaimer
)
"""


def upgrade() -> None:
    # agent_runs
    op.add_column("agent_runs", sa.Column("provider", sa.String(20)))
    op.add_column(
        "agent_runs",
        sa.Column("params", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "agent_runs",
        sa.Column("steps", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "agent_runs", sa.Column("llm_calls", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("agent_runs", sa.Column("cost_usd", sa.Numeric(12, 6)))
    op.create_check_constraint(
        "ck_agent_runs_provider", "agent_runs", f"provider IS NULL OR provider IN {PROVIDERS}"
    )
    op.create_check_constraint("ck_agent_runs_llm_calls", "agent_runs", "llm_calls >= 0")
    op.create_check_constraint(
        "ck_agent_runs_cost_usd", "agent_runs", "cost_usd IS NULL OR cost_usd >= 0"
    )
    op.create_check_constraint("ck_agent_runs_status", "agent_runs", f"status IN {RUN_STATUSES}")
    op.drop_index("ix_agent_runs_user_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_created_at", table_name="agent_runs")
    op.create_index(
        "ix_agent_runs_user_id_created_at", "agent_runs", ["user_id", "created_at"]
    )

    # suggestions
    op.add_column(
        "suggestions",
        sa.Column("source", sa.String(10), nullable=False, server_default="ai"),
    )
    op.add_column(
        "suggestions",
        sa.Column("ai_status", sa.String(20), nullable=False, server_default="ok"),
    )
    op.add_column(
        "suggestions",
        sa.Column("params", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column("suggestions", sa.Column("provider", sa.String(20)))
    op.add_column("suggestions", sa.Column("report", JSONB()))
    op.create_check_constraint("ck_suggestions_source", "suggestions", "source IN ('ai','rules')")
    op.create_check_constraint(
        "ck_suggestions_provider", "suggestions", f"provider IS NULL OR provider IN {PROVIDERS}"
    )
    op.execute(BACKFILL_REPORT)
    op.alter_column("suggestions", "report", nullable=False)
    op.alter_column("suggestions", "rationale", nullable=True)
    op.drop_index("ix_suggestions_user_id", table_name="suggestions")
    op.drop_index("ix_suggestions_created_at", table_name="suggestions")
    op.create_index(
        "ix_suggestions_user_id_created_at", "suggestions", ["user_id", "created_at"]
    )

    # llm_usage_daily
    op.create_table(
        "llm_usage_daily",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
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


def downgrade() -> None:
    op.drop_table("llm_usage_daily")

    op.drop_index("ix_suggestions_user_id_created_at", table_name="suggestions")
    op.create_index("ix_suggestions_user_id", "suggestions", ["user_id"])
    op.create_index("ix_suggestions_created_at", "suggestions", ["created_at"])
    op.execute("UPDATE suggestions SET rationale = '[]'::jsonb WHERE rationale IS NULL")
    op.alter_column("suggestions", "rationale", nullable=False)
    op.drop_constraint("ck_suggestions_provider", "suggestions", type_="check")
    op.drop_constraint("ck_suggestions_source", "suggestions", type_="check")
    for col in ("report", "provider", "params", "ai_status", "source"):
        op.drop_column("suggestions", col)

    op.drop_index("ix_agent_runs_user_id_created_at", table_name="agent_runs")
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index("ix_agent_runs_created_at", "agent_runs", ["created_at"])
    for name in ("status", "cost_usd", "llm_calls", "provider"):
        op.drop_constraint(f"ck_agent_runs_{name}", "agent_runs", type_="check")
    for col in ("cost_usd", "llm_calls", "steps", "params", "provider"):
        op.drop_column("agent_runs", col)
