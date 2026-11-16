import datetime as dt
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import InstrumentedAttribute, Session, load_only

from coffer.agent.models import AgentRun, LlmUsageDaily, Suggestion
from coffer.agent.schemas import (
    ActionReport,
    AgentRunListItem,
    AgentRunOut,
    Finding,
    Source,
    SuggestionOut,
)

Order = Literal["asc", "desc"]
RunSort = Literal["created_at", "duration_ms", "cost_usd", "tokens"]


# --- daily limit (atomic) ---------------------------------------------------------------------


def reserve_run(db: Session, user_id: int, now: datetime, limit: int) -> bool:
    """Atomically take one of the user's daily model runs (UTC day); False when none is left.

    A single INSERT ... ON CONFLICT DO UPDATE ... WHERE runs < limit RETURNING: concurrent
    callers serialize on the row, so exactly `limit` of them succeed. Commits.
    """
    if limit <= 0:
        return False
    day = now.astimezone(UTC).date()
    stmt = insert(LlmUsageDaily).values(user_id=user_id, day=day, runs=1)
    stmt = stmt.on_conflict_do_update(
        index_elements=[LlmUsageDaily.user_id, LlmUsageDaily.day],
        set_={"runs": LlmUsageDaily.runs + 1},
        where=LlmUsageDaily.runs < limit,
    ).returning(LlmUsageDaily.runs)
    reserved = db.execute(stmt).scalar_one_or_none() is not None
    db.commit()
    return reserved


def record_usage(
    db: Session, user_id: int, day: dt.date, input_tokens: int, output_tokens: int
) -> None:
    """Add the tokens of a finished run to the day's counter (no commit)."""
    db.execute(
        update(LlmUsageDaily)
        .where(LlmUsageDaily.user_id == user_id, LlmUsageDaily.day == day)
        .values(
            input_tokens=LlmUsageDaily.input_tokens + input_tokens,
            output_tokens=LlmUsageDaily.output_tokens + output_tokens,
        )
    )


# --- writes ------------------------------------------------------------------------------------


def add_run(db: Session, **fields: Any) -> AgentRun:
    """Persist one run trace (N09); flushed, the caller commits."""
    run = AgentRun(**fields)
    db.add(run)
    db.flush()
    return run


def add_suggestion(db: Session, **fields: Any) -> Suggestion:
    suggestion = Suggestion(**fields)
    db.add(suggestion)
    db.flush()
    return suggestion


# --- history -----------------------------------------------------------------------------------


def _legacy_report(s: Suggestion) -> ActionReport:
    """Report of a row without one (not expected after migration 0007, kept defensive)."""
    findings = [
        Finding(
            title=str(r.get("claim") or "—"),
            refers_to=r.get("refers_to") or "budget",
            value=r.get("value"),
        )
        for r in (s.rationale or [])
    ]
    return ActionReport(
        headline=s.summary,
        findings=findings,
        risks=s.risks or [],
        sources=[
            Source(title=x.get("title") or x["url"], url=x["url"], fetched_at=s.created_at)
            for x in (s.sources or [])
            if x.get("url")
        ],
        disclaimer=s.disclaimer,
    )


def suggestion_out(s: Suggestion) -> SuggestionOut:
    try:
        report = ActionReport.model_validate(s.report) if s.report else _legacy_report(s)
    except ValidationError:
        report = _legacy_report(s)
    return SuggestionOut(
        id=s.id,
        action=s.type,
        source=s.source,  # type: ignore[arg-type]
        ai_status=s.ai_status,
        headline=s.summary,
        report=report,
        params=s.params or {},
        model=s.model if s.source == "ai" else None,
        provider=s.provider,
        run_id=s.agent_run_id,
        created_at=s.created_at,
        profile_used=s.profile_snapshot is not None,
    )


@dataclass(frozen=True)
class SuggestionFilters:
    action: str | None = None
    source: Literal["ai", "rules"] | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    q: str | None = None
    order: Order = "desc"
    limit: int = 5
    offset: int = 0


@dataclass(frozen=True)
class RunFilters:
    action: str | None = None
    status: str | None = None
    provider: str | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    sort: RunSort = "created_at"
    order: Order = "desc"
    limit: int = 20
    offset: int = 0


def _day_bounds(
    column: InstrumentedAttribute[datetime], date_from: dt.date | None, date_to: dt.date | None
) -> list[ColumnElement[bool]]:
    """Inclusive date range on a timestamptz column, days taken in UTC."""
    out: list[ColumnElement[bool]] = []
    if date_from is not None:
        out.append(column >= datetime.combine(date_from, dt.time.min, UTC))
    if date_to is not None:
        out.append(column < datetime.combine(date_to, dt.time.min, UTC) + timedelta(days=1))
    return out


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_suggestions(
    db: Session, user_id: int, f: SuggestionFilters
) -> tuple[list[SuggestionOut], int]:
    conditions: list[ColumnElement[bool]] = [Suggestion.user_id == user_id]
    if f.action:
        conditions.append(Suggestion.type == f.action)
    if f.source:
        conditions.append(Suggestion.source == f.source)
    if f.q:
        conditions.append(Suggestion.summary.ilike(f"%{_escape_like(f.q)}%", escape="\\"))
    conditions += _day_bounds(Suggestion.created_at, f.date_from, f.date_to)
    total = db.scalar(select(func.count()).select_from(Suggestion).where(*conditions)) or 0
    ordering = (
        (Suggestion.created_at.asc(), Suggestion.id.asc())
        if f.order == "asc"
        else (Suggestion.created_at.desc(), Suggestion.id.desc())
    )
    stmt = select(Suggestion).where(*conditions).order_by(*ordering).limit(f.limit).offset(f.offset)
    return [suggestion_out(s) for s in db.scalars(stmt)], total


def get_suggestion(db: Session, user_id: int, suggestion_id: int) -> SuggestionOut | None:
    s = db.scalar(
        select(Suggestion).where(Suggestion.id == suggestion_id, Suggestion.user_id == user_id)
    )
    return None if s is None else suggestion_out(s)


_suggestion_id = (
    select(Suggestion.id)
    .where(Suggestion.agent_run_id == AgentRun.id)
    .order_by(Suggestion.id)
    .limit(1)
    .correlate(AgentRun)
    .scalar_subquery()
)
_tool_calls_count = func.jsonb_array_length(AgentRun.tool_calls)
_tokens = func.coalesce(AgentRun.input_tokens, 0) + func.coalesce(AgentRun.output_tokens, 0)
_LIST_COLUMNS = (
    AgentRun.id,
    AgentRun.user_id,
    AgentRun.task,
    AgentRun.status,
    AgentRun.provider,
    AgentRun.model,
    AgentRun.llm_calls,
    AgentRun.input_tokens,
    AgentRun.output_tokens,
    AgentRun.cost_usd,
    AgentRun.duration_ms,
    AgentRun.created_at,
)


def _list_item(run: AgentRun, tool_calls_count: int, suggestion_id: int | None) -> dict[str, Any]:
    cost: Decimal | None = run.cost_usd
    return {
        "id": run.id,
        "action": run.task,
        "status": run.status,
        "provider": run.provider,
        "model": run.model,
        "llm_calls": run.llm_calls,
        "tool_calls_count": tool_calls_count,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "cost_usd": None if cost is None else f"{cost:f}",
        "duration_ms": run.duration_ms,
        "created_at": run.created_at,
        "suggestion_id": suggestion_id,
    }


def list_runs(db: Session, user_id: int, f: RunFilters) -> tuple[list[AgentRunListItem], int]:
    conditions: list[ColumnElement[bool]] = [AgentRun.user_id == user_id]
    if f.action:
        conditions.append(AgentRun.task == f.action)
    if f.status:
        conditions.append(AgentRun.status == f.status)
    if f.provider:
        conditions.append(AgentRun.provider == f.provider)
    conditions += _day_bounds(AgentRun.created_at, f.date_from, f.date_to)
    total = db.scalar(select(func.count()).select_from(AgentRun).where(*conditions)) or 0
    column: ColumnElement[Any] = {
        "created_at": AgentRun.created_at,
        "duration_ms": AgentRun.duration_ms,
        "cost_usd": AgentRun.cost_usd,
        "tokens": _tokens,
    }[f.sort]
    primary = column.asc().nulls_last() if f.order == "asc" else column.desc().nulls_last()
    tiebreak = AgentRun.id.asc() if f.order == "asc" else AgentRun.id.desc()
    stmt = (
        select(AgentRun, _tool_calls_count, _suggestion_id)
        .options(load_only(*_LIST_COLUMNS))
        .where(*conditions)
        .order_by(primary, tiebreak)
        .limit(f.limit)
        .offset(f.offset)
    )
    items = [
        AgentRunListItem(**_list_item(run, count, sid)) for run, count, sid in db.execute(stmt)
    ]
    return items, total


def get_run(db: Session, user_id: int, run_id: int) -> AgentRunOut | None:
    row = db.execute(
        select(AgentRun, _suggestion_id).where(AgentRun.id == run_id, AgentRun.user_id == user_id)
    ).one_or_none()
    if row is None:
        return None
    run, suggestion_id = row
    return AgentRunOut(
        **_list_item(run, len(run.tool_calls or []), suggestion_id),
        params=run.params or {},
        prompt_version=run.prompt_version,
        steps=run.steps or [],
        messages=run.messages or [],
        raw_outputs=run.raw_outputs or [],
        validation_errors=run.validation_errors or [],
        error=run.error,
        tool_calls=run.tool_calls or [],
    )
