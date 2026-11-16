"""The one action interface (E5-00 K1): every AI feature is an `Action` run by `agent.runner`."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from coffer.agent.schemas import Fact, ParamSpec, ReportDraft, Source, Table
from coffer.agent.validator import Seen

__all__ = ["Action", "ActionContext", "ParamSpec", "Prepared", "no_checks", "no_finalize"]


class ToolCallFailed(Exception):
    """A tool called from `prepare` returned an error (the deterministic part cannot go on)."""


@dataclass(frozen=True)
class ActionContext:
    db: Session
    user_id: int
    now: datetime
    # Runs a tool through the registry and records it in the trace; returns the output dict
    # and raises ToolCallFailed when the tool reported an error.
    call: Callable[[str, dict[str, Any]], dict[str, Any]]

    def try_call(self, name: str, args: dict[str, Any]) -> dict[str, Any] | None:
        """Like `call`, but a failing tool gives None (for optional data)."""
        try:
            return self.call(name, args)
        except ToolCallFailed:
            return None


@dataclass(frozen=True)
class Prepared:
    """Deterministic part of a run: what the user sees as facts/tables and what the model gets."""

    facts: list[Fact] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)  # JSON for the model: aggregates only
    snapshot: dict[str, Any] = field(default_factory=dict)  # -> suggestions.data_snapshot
    profile_snapshot: dict[str, Any] | None = None
    no_data: str | None = None  # Polish message: the run ends without a model, status no_data


def no_checks(draft: ReportDraft, prepared: Prepared, seen: Seen) -> list[str]:
    return []


def no_finalize(draft: ReportDraft, prepared: Prepared) -> None:
    return None


@dataclass(frozen=True)
class Action:
    id: str  # snake_case, <= 30 chars (agent_runs.task / suggestions.type)
    name: str
    description: str
    params_model: type[BaseModel]
    params_ui: tuple[ParamSpec, ...]
    prompt_version: str  # file agent/prompts/<prompt_version>.md (system prompt)
    tools: tuple[str, ...]  # registry names the MODEL may call
    draft_model: type[ReportDraft]
    disclaimer: str
    uses_user_data: bool
    uses_internet: bool
    prepare: Callable[[ActionContext, Any], Prepared]
    fallback: Callable[[Prepared, Any], ReportDraft]  # result without AI, always possible
    check: Callable[[ReportDraft, Prepared, Seen], list[str]] = no_checks
    # Runs once on a draft that passed validation: normalizes it from deterministic data
    # (e.g. fields taken from an allowed list instead of the model's answer).
    finalize: Callable[[ReportDraft, Prepared], None] = no_finalize
    max_steps: int = 5  # max model calls in one run
