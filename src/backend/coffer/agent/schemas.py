from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DISCLAIMER = (
    "To jest sugestia informacyjna, a nie porada inwestycyjna. Decyzję podejmujesz samodzielnie."
)

AiStatus = Literal["ok", "unavailable", "limited", "timeout", "invalid", "no_data"]
ParamKind = Literal["month", "text", "symbol", "amount", "quantity", "int", "select"]
ValueKind = Literal["money", "percent", "number", "text", "date"]


# --- report (E5-00 K2): facts and tables come from code, the model only writes the narration --


class Fact(BaseModel):
    label: str
    value: str
    kind: ValueKind


class TableColumn(BaseModel):
    key: str
    label: str
    kind: ValueKind


class Table(BaseModel):
    id: str
    title: str
    columns: list[TableColumn]
    rows: list[dict[str, str]]


def is_http_url(value: object) -> bool:
    """Only plain web links may reach the UI (no javascript:, data:, file: ...)."""
    return isinstance(value, str) and value.lower().startswith(("http://", "https://"))


def _http_only(value: str | None) -> str | None:
    if value is not None and not is_http_url(value):
        raise ValueError("Adres musi zaczynać się od http:// lub https://")
    return value


class Finding(BaseModel):
    title: str = Field(min_length=1)
    detail: str = ""
    refers_to: Literal["budget", "profile", "portfolio", "market", "calc"]
    value: str | None = None


class Recommendation(BaseModel):
    title: str = Field(min_length=1)
    detail: str = ""
    symbol: str | None = None
    asset_class: str | None = None
    amount: str | None = None
    risk_level: int | None = Field(default=None, ge=1, le=5)
    source_url: str | None = None

    _check_url = field_validator("source_url")(_http_only)


class Source(BaseModel):
    title: str
    url: str
    publisher: str | None = None
    published_at: str | None = None
    fetched_at: datetime

    @field_validator("url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        return _http_only(value) or value


class ReportDraft(BaseModel):
    """Model answer (and fallback result): the narrative part of a report."""

    headline: str = Field(min_length=1, max_length=200)
    findings: list[Finding] = Field(min_length=1, max_length=6)
    recommendations: list[Recommendation] = Field(default_factory=list, max_length=5)
    risks: list[str] = Field(default_factory=list, max_length=5)
    source_urls: list[str] = Field(default_factory=list, max_length=10)


class ActionReport(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def _drop_bad_links(cls, data: Any) -> Any:
        """Stored rows (older versions, manual edits) never break reading: sources with a
        non-http(s) URL are dropped and a bad recommendation link is cleared."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        data["sources"] = [
            s
            for s in data.get("sources") or []
            if not isinstance(s, dict) or is_http_url(s.get("url"))
        ]
        recs = []
        for r in data.get("recommendations") or []:
            if isinstance(r, dict) and r.get("source_url") and not is_http_url(r["source_url"]):
                r = {**r, "source_url": None}
            recs.append(r)
        data["recommendations"] = recs
        return data

    headline: str
    facts: list[Fact] = []
    tables: list[Table] = []
    findings: list[Finding] = []
    recommendations: list[Recommendation] = []
    risks: list[str] = []
    sources: list[Source] = []
    disclaimer: str = DISCLAIMER


# --- actions and tools catalogue ---------------------------------------------------------------


class ParamSpec(BaseModel):
    """One field of an action's parameter form (rendered by the frontend)."""

    model_config = ConfigDict(frozen=True)

    name: str
    label: str
    kind: ParamKind
    required: bool = False
    default: str | int | None = None
    options: tuple[str, ...] = ()
    help: str | None = None


class ActionInfoOut(BaseModel):
    id: str
    name: str
    description: str
    params: list[ParamSpec]
    tools: list[str]
    uses_user_data: bool
    uses_internet: bool


class ToolInfoOut(BaseModel):
    name: str
    description: str
    group: Literal["user_data", "market", "calc"]
    uses_internet: bool
    parameters: dict[str, Any]


class RunRequest(BaseModel):
    params: dict[str, Any] = {}


# --- results, history, traces ------------------------------------------------------------------


class ActionRunOut(BaseModel):
    action: str
    run_id: int | None
    suggestion_id: int | None
    ai_status: AiStatus
    source: Literal["ai", "rules", "none"]
    report: ActionReport
    model: str | None
    provider: str | None
    duration_ms: int


class SuggestionOut(BaseModel):
    id: int
    action: str
    source: Literal["ai", "rules"]
    ai_status: str
    headline: str
    report: ActionReport
    params: dict[str, Any]
    model: str | None
    provider: str | None
    run_id: int | None
    created_at: datetime
    profile_used: bool


class SuggestionListOut(BaseModel):
    items: list[SuggestionOut]
    total: int


class AgentStatusOut(BaseModel):
    provider: Literal["ollama", "openai", "gemini", "anthropic", "none"]
    model: str | None
    available: bool


class AgentRunListItem(BaseModel):
    id: int
    action: str
    status: str
    provider: str | None
    model: str | None
    llm_calls: int
    tool_calls_count: int
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: str | None
    duration_ms: int | None
    created_at: datetime
    suggestion_id: int | None


class AgentRunOut(AgentRunListItem):
    params: dict[str, Any]
    prompt_version: str
    steps: list[dict[str, Any]]
    messages: list[dict[str, Any]]
    raw_outputs: list[str]
    validation_errors: list[str]
    error: str | None
    tool_calls: list[dict[str, Any]]


class AgentRunListOut(BaseModel):
    items: list[AgentRunListItem]
    total: int
