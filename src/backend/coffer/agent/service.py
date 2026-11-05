from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from coffer.agent.models import AgentRun, Suggestion
from coffer.agent.schemas import SuggestionOut


def suggestion_out(s: Suggestion) -> SuggestionOut:
    return SuggestionOut(
        id=s.id,
        type=s.type,
        month=s.month,
        summary=s.summary,
        rationale=s.rationale,  # type: ignore[arg-type]
        risks=s.risks or [],
        disclaimer=s.disclaimer,
        model=s.model,
        generated_at=s.created_at,
        duration_ms=s.duration_ms,
        profile_used=s.profile_snapshot is not None,
    )


def count_runs_today(db: Session, user_id: int) -> int:
    """Runs of the current UTC day that actually called the model (attempts > 0)."""
    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count(AgentRun.id)).where(
        AgentRun.user_id == user_id,
        AgentRun.attempts > 0,
        AgentRun.created_at >= day_start,
    )
    return db.scalar(stmt) or 0


def list_suggestions(db: Session, user_id: int, limit: int) -> list[Suggestion]:
    stmt = (
        select(Suggestion)
        .where(Suggestion.user_id == user_id)
        .order_by(Suggestion.created_at.desc(), Suggestion.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def get_suggestion(db: Session, user_id: int, suggestion_id: int) -> Suggestion | None:
    return db.scalar(
        select(Suggestion).where(Suggestion.id == suggestion_id, Suggestion.user_id == user_id)
    )


def list_runs(db: Session, user_id: int, limit: int) -> list[AgentRun]:
    stmt = (
        select(AgentRun)
        .where(AgentRun.user_id == user_id)
        .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def get_run(db: Session, user_id: int, run_id: int) -> AgentRun | None:
    return db.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id))
