import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from coffer.core.db import Base

_PROVIDERS = "('ollama','openai','gemini','anthropic')"
_RUN_STATUSES = "('ok','invalid','unavailable','limited','timeout','no_data','error','no_surplus')"


class AgentRun(Base):
    """Trace of one agent/workflow run: what was sent, which tools ran, what came back (N09)."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            f"provider IS NULL OR provider IN {_PROVIDERS}", name="ck_agent_runs_provider"
        ),
        CheckConstraint("llm_calls >= 0", name="ck_agent_runs_llm_calls"),
        CheckConstraint("cost_usd IS NULL OR cost_usd >= 0", name="ck_agent_runs_cost_usd"),
        CheckConstraint(f"status IN {_RUN_STATUSES}", name="ck_agent_runs_status"),
        Index("ix_agent_runs_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    task: Mapped[str] = mapped_column(String(30))  # e.g. "surplus"
    prompt_version: Mapped[str] = mapped_column(String(30))  # e.g. "surplus_v2"
    model: Mapped[str | None] = mapped_column(String(100))
    # ok | no_surplus | unavailable | invalid | limited
    status: Mapped[str] = mapped_column(String(20))
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    raw_outputs: Mapped[list[str]] = mapped_column(JSONB, default=list)
    validation_errors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    provider: Mapped[str | None] = mapped_column(String(20))
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    steps: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    llm_calls: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Suggestion(Base):
    """A validated suggestion shown to the user. Immutable: profile changes do not alter it."""

    __tablename__ = "suggestions"
    __table_args__ = (
        CheckConstraint("source IN ('ai','rules')", name="ck_suggestions_source"),
        CheckConstraint(
            f"provider IS NULL OR provider IN {_PROVIDERS}", name="ck_suggestions_provider"
        ),
        Index("ix_suggestions_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    agent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(String(30))  # "surplus"
    month: Mapped[str | None] = mapped_column(String(7))
    summary: Mapped[str] = mapped_column(Text)
    # Legacy layout (pre-E5); new rows keep everything in `report`.
    rationale: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(10), default="ai", server_default="ai")
    ai_status: Mapped[str] = mapped_column(String(20), default="ok", server_default="ok")
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    provider: Mapped[str | None] = mapped_column(String(20))
    risks: Mapped[list[str]] = mapped_column(JSONB, default=list)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    disclaimer: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(100))
    profile_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    data_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LlmUsageDaily(Base):
    """Atomic per-user daily LLM counter (reserve_run), day in UTC."""

    __tablename__ = "llm_usage_daily"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "day", name="pk_llm_usage_daily"),
        CheckConstraint("runs >= 0", name="ck_llm_usage_daily_runs"),
        CheckConstraint("input_tokens >= 0", name="ck_llm_usage_daily_input_tokens"),
        CheckConstraint("output_tokens >= 0", name="ck_llm_usage_daily_output_tokens"),
        Index("ix_llm_usage_daily_day", "day"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    day: Mapped[dt.date] = mapped_column(Date)
    runs: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
