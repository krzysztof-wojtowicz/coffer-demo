import datetime as dt
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from coffer.core.db import Base


class AgentRun(Base):
    """Trace of one agent/workflow run: what was sent, which tools ran, what came back (N09)."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
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
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Suggestion(Base):
    """A validated suggestion shown to the user. Immutable: profile changes do not alter it."""

    __tablename__ = "suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(String(30))  # "surplus"
    month: Mapped[str | None] = mapped_column(String(7))
    summary: Mapped[str] = mapped_column(Text)
    rationale: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    risks: Mapped[list[str]] = mapped_column(JSONB, default=list)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    disclaimer: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(100))
    profile_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    data_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
