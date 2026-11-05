from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from coffer.budget.schemas import MonthSummaryOut
from coffer.core.months import MonthStr

DISCLAIMER = (
    "To jest sugestia informacyjna, a nie porada inwestycyjna. Decyzję podejmujesz samodzielnie."
)


class RationaleItemOut(BaseModel):
    claim: str
    refers_to: Literal["budget", "profile", "portfolio"]
    value: str


class SuggestionOut(BaseModel):
    id: int
    type: str
    month: str | None
    summary: str
    rationale: list[RationaleItemOut]
    risks: list[str]
    disclaimer: str
    model: str
    generated_at: datetime
    duration_ms: int | None
    profile_used: bool


class SurplusRequest(BaseModel):
    month: MonthStr


class SurplusSuggestionOut(BaseModel):
    summary: MonthSummaryOut
    ai_status: Literal["ok", "no_surplus", "unavailable", "limited"]
    suggestion: SuggestionOut | None = None
    run_id: int | None = None


class AgentStatusOut(BaseModel):
    provider: Literal["ollama", "none"]
    model: str | None
    available: bool


class AgentRunListItem(BaseModel):
    id: int
    task: str
    status: str
    model: str | None
    attempts: int
    duration_ms: int | None
    created_at: datetime


class AgentRunOut(AgentRunListItem):
    prompt_version: str
    tool_calls: list[dict[str, Any]]
    messages: list[dict[str, Any]]
    raw_outputs: list[str]
    validation_errors: list[str]
    error: str | None
    input_tokens: int | None
    output_tokens: int | None
