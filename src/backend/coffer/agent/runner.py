"""The one engine that runs every action (E5-00 D1-D5).

prepare (DB, deterministic) -> no_data? -> LLM configured? -> daily limit -> release the DB
connection -> tool-calling loop (structured output, one time budget) -> validation with retries
-> rule-based fallback on any failure -> trace, usage and suggestion saved.
The model never decides anything numeric: facts and tables come from `prepare`.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from coffer.agent import service
from coffer.agent.actions.base import Action, ActionContext, Prepared, ToolCallFailed
from coffer.agent.guard import guard
from coffer.agent.llm import (
    LLMClient,
    LLMMessage,
    LLMTimeout,
    LLMUnavailable,
    llm_deadline,
    remaining_s,
)
from coffer.agent.schemas import ActionReport, ActionRunOut, ReportDraft, Source
from coffer.agent.tools.registry import (
    ToolArgumentError,
    ToolContext,
    ToolRegistry,
    UnknownTool,
)
from coffer.agent.trace import RunTrace
from coffer.agent.validator import Seen, validate_draft
from coffer.core.config import get_settings

log = logging.getLogger(__name__)

AgentEvent = dict[str, Any]
RunStatus = Literal["ok", "invalid", "unavailable", "limited", "timeout", "no_data", "error"]

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
PROVIDERS = ("ollama", "openai", "gemini", "anthropic")
# Statuses whose rule-based result is shown and kept in the history (D6).
FALLBACK_STATUSES = ("unavailable", "limited", "timeout", "invalid")
FAILURE_MESSAGE = "Nie udało się wykonać akcji"


def noop(event: AgentEvent) -> None:
    return None


class ActionFailed(Exception):
    """Unexpected failure; the run was recorded with status `error`."""


@dataclass
class _Outcome:
    status: RunStatus
    draft: ReportDraft | None = None
    error: str | None = None


# --- prompt and protocol -----------------------------------------------------------------------


@cache
def load_prompt(version: str) -> str:
    return (PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")


def system_prompt(action: Action, registry: ToolRegistry) -> str:
    tools = "\n".join(
        f"- {t.name}: {t.description} Argumenty (JSON Schema): "
        f"{json.dumps(t.input_model.model_json_schema(), ensure_ascii=False)}"
        for t in (registry.get(n) for n in action.tools)
        if t is not None
    )
    protocol = (
        "Odpowiadasz wyłącznie obiektem JSON. Dane do analizy dostajesz w pierwszej wiadomości."
        + (
            f"\nMożesz pobrać dodatkowe dane narzędziami:\n{tools}\n"
            'Aby wywołać narzędzie, zwróć {"action":"call_tool","tool":"<nazwa>","args":{...}}; '
            "wynik dostaniesz w kolejnej wiadomości.\n"
            if tools
            else "\n"
        )
        + 'Gdy masz dane, zwróć {"action":"final","answer":{...}} w formacie z instrukcji. '
        f"Masz maksymalnie {action.max_steps} wywołań."
    )
    return load_prompt(action.prompt_version) + "\n\n" + protocol


def response_schema(action: Action, registry: ToolRegistry) -> dict[str, Any]:
    """JSON Schema of one model step: `{"action": ..., "tool"?, "args"?, "answer"?}`."""
    answer = action.draft_model.model_json_schema()
    defs: dict[str, Any] = dict(answer.pop("$defs", {}))
    props: dict[str, Any] = {
        "action": {"type": "string", "enum": ["call_tool", "final"] if action.tools else ["final"]},
        "answer": answer,
    }
    if action.tools:
        props["tool"] = {"type": "string", "enum": list(action.tools)}
        arg_props: dict[str, Any] = {}
        for name in action.tools:
            tool = registry.get(name)
            if tool is None:
                continue
            tool_schema = tool.input_model.model_json_schema()
            defs.update(tool_schema.pop("$defs", {}))
            arg_props.update(tool_schema.get("properties", {}))
        if arg_props:
            props["args"] = {"type": "object", "properties": arg_props}
    schema: dict[str, Any] = {"type": "object", "properties": props, "required": ["action"]}
    if defs:
        schema["$defs"] = defs
    return schema


def _correction(errors: list[str]) -> str:
    return (
        "Odpowiedź nie przeszła walidacji: "
        + "; ".join(errors)
        + ". Popraw ją i odpowiedz ponownie w tym samym formacie JSON."
    )


def _format_errors(exc: ValidationError) -> list[str]:
    return [
        f"Niepoprawny format odpowiedzi ({'.'.join(str(p) for p in e['loc'])}: {e['msg']})"
        for e in exc.errors()
    ]


# --- model phase -------------------------------------------------------------------------------


def _model_phase(
    *,
    action: Action,
    prepared: Prepared,
    llm: LLMClient,
    registry: ToolRegistry,
    tool_ctx: ToolContext,
    db: Session,
    trace: RunTrace,
    seen: Seen,
    on_event: Callable[[AgentEvent], None],
) -> _Outcome:
    settings = get_settings()
    system = system_prompt(action, registry)
    schema = response_schema(action, registry)
    first = "Dane do analizy (JSON):\n" + json.dumps(prepared.context, ensure_ascii=False)
    conversation = [LLMMessage("user", first)]
    trace.messages.append({"role": "system", "content": system})
    trace.messages.append({"role": "user", "content": first})
    invalid = 0

    def reply(content: str, role: Literal["user", "assistant"]) -> None:
        conversation.append(LLMMessage(role, content))
        trace.messages.append({"role": role, "content": content})

    try:
        # One budget for all model calls (retries and fallback chain included): the request
        # must end well before the 120 s proxy limit.
        with llm_deadline(settings.agent_timeout_s):
            for step in range(action.max_steps):
                left = remaining_s()
                if left is not None and left <= 0:
                    raise LLMTimeout("Przekroczono limit czasu akcji")
                started = trace.now_ms()
                try:
                    response = llm.complete(
                        system=system, messages=conversation, response_schema=schema
                    )
                except LLMUnavailable as exc:
                    trace.llm_error(str(exc), started, step + 1)
                    left = remaining_s()
                    if isinstance(exc, LLMTimeout) or (left is not None and left <= 0):
                        raise LLMTimeout(str(exc)) from exc
                    raise
                trace.llm(response, started, step + 1)
                reply(response.content, "assistant")

                errors: list[str] = []
                try:
                    data = json.loads(response.content)
                except (TypeError, ValueError):
                    data = None
                kind = data.get("action") if isinstance(data, dict) else None
                if kind == "call_tool" and isinstance(data, dict):
                    left = remaining_s()
                    if left is not None and left <= 0:  # no time for another tool round
                        raise LLMTimeout("Przekroczono limit czasu akcji")
                    result = _call_model_tool(data, action, registry, tool_ctx, db, trace, seen)
                    hint = (
                        '\nTo ostatni krok: zwróć {"action":"final", ...}.'
                        if step >= action.max_steps - 2
                        else ""
                    )
                    reply(f"Wynik narzędzia {data.get('tool')}:\n{result}{hint}", "user")
                    continue
                if kind == "final" and isinstance(data, dict):
                    checked_at = trace.now_ms()
                    try:
                        draft = action.draft_model.model_validate(data.get("answer"))
                        errors = validate_draft(draft, seen) + action.check(draft, prepared, seen)
                    except ValidationError as exc:
                        draft, errors = None, _format_errors(exc)
                    trace.validation(errors, checked_at)
                    if not errors and draft is not None:
                        action.finalize(draft, prepared)
                        return _Outcome("ok", draft)
                else:
                    errors = [
                        'Odpowiedź musi być obiektem JSON z polem "action": call_tool lub final.'
                    ]
                    trace.validation(errors, trace.now_ms())
                invalid += 1
                if invalid >= settings.agent_max_attempts:
                    return _Outcome("invalid")
                on_event({"type": "status", "message": "Poprawiam odpowiedź…"})
                reply(_correction(errors), "user")
        return _Outcome("invalid", error="Przekroczono limit kroków")
    except LLMTimeout as exc:
        return _Outcome("timeout", error=str(exc))
    except LLMUnavailable as exc:
        return _Outcome("unavailable", error=str(exc))


def _call_model_tool(
    data: dict[str, Any],
    action: Action,
    registry: ToolRegistry,
    tool_ctx: ToolContext,
    db: Session,
    trace: RunTrace,
    seen: Seen,
) -> str:
    """Run a tool the model asked for; returns the JSON text for the model (errors included)."""
    name = str(data.get("tool") or "")
    raw_args = data.get("args")
    args: dict[str, Any] = raw_args if isinstance(raw_args, dict) else {}
    started = trace.now_ms()
    output: dict[str, Any]
    if name not in action.tools:
        message = f"Narzędzie {name or '?'} nie jest dostępne w tej akcji. Dostępne: " + ", ".join(
            action.tools
        )
        trace.tool_error(name, args, message, started, "model")
        output = {"error": message}
    else:
        try:
            call = registry.call(name, args, tool_ctx)
        except (UnknownTool, ToolArgumentError) as exc:
            message = f"Niepoprawne wywołanie narzędzia {name}: {exc}"
            trace.tool_error(name, args, message, started, "model")
            output = {"error": message}
        else:
            trace.tool(call, started, "model")
            output = call.output
            if call.status == "ok":
                seen.add(output)
    # Reads only: end the transaction so the connection is not held while the model thinks.
    if "error" in output:
        db.rollback()
    else:
        db.commit()
    return json.dumps(output, ensure_ascii=False)


# --- result ------------------------------------------------------------------------------------


def _report(
    action: Action, prepared: Prepared, draft: ReportDraft, seen: Seen, now: datetime
) -> ActionReport:
    sources = list(prepared.sources)
    known = {s.url for s in sources}
    for url in draft.source_urls:
        if url in seen.urls and url not in known:
            known.add(url)
            sources.append(Source(title=seen.titles.get(url, url), url=url, fetched_at=now))
    return ActionReport(
        headline=draft.headline,
        facts=prepared.facts,
        tables=prepared.tables,
        findings=draft.findings,
        recommendations=draft.recommendations,
        risks=draft.risks,
        sources=sources,
        disclaimer=action.disclaimer,
    )


def run_action(
    db: Session,
    user_id: int,
    action: Action,
    params: BaseModel,
    llm: LLMClient | None,
    registry: ToolRegistry,
    on_event: Callable[[AgentEvent], None] = noop,
) -> ActionRunOut:
    """Run one action under the abuse guard (call budget, parallel-run cap).

    Raises ActionRateLimited before anything is fetched or recorded when the user is over it.
    """
    guard.acquire(user_id)
    try:
        return _run_action(db, user_id, action, params, llm, registry, on_event)
    finally:
        guard.release(user_id)


def _run_action(
    db: Session,
    user_id: int,
    action: Action,
    params: BaseModel,
    llm: LLMClient | None,
    registry: ToolRegistry,
    on_event: Callable[[AgentEvent], None] = noop,
) -> ActionRunOut:
    """Run one action and persist the trace.

    Always returns a result (rule-based when the model is missing, limited, slow or wrong);
    raises ActionFailed only on an unexpected error, after recording the run as `error`.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    trace = RunTrace(on_step=lambda step: on_event({"type": "step", "data": step}))
    seen = Seen()
    tool_ctx = ToolContext(db=db, user_id=user_id, now=now)

    def call(name: str, args: dict[str, Any]) -> dict[str, Any]:
        started = trace.now_ms()
        result = registry.call(name, args, tool_ctx)
        trace.tool(result, started, "prepare")
        seen.add(result.output)
        if result.status == "error":
            raise ToolCallFailed(result.error)
        return result.output

    prepared = Prepared()
    draft: ReportDraft | None = None
    outcome = _Outcome("error")
    reserved = False
    try:
        on_event({"type": "status", "message": "Liczę dane…"})
        try:
            prepared = action.prepare(ActionContext(db, user_id, now, call), params)
        except ToolCallFailed as exc:
            # A data tool failed in the deterministic part: no report is possible, but this is
            # not a server error. End like no_data with the tool's Polish message (not saved).
            prepared = Prepared(no_data=str(exc) or FAILURE_MESSAGE)
        seen.add(prepared.context)
        if prepared.no_data is not None:
            outcome = _Outcome("no_data")
        elif llm is None:
            outcome = _Outcome("unavailable")
        elif not service.reserve_run(db, user_id, now, settings.agent_daily_limit):
            trace.limit(trace.now_ms())
            outcome = _Outcome("limited")
        else:
            reserved = True
            # The model can take tens of seconds: give the connection back to the pool (N08).
            # The same session is reused afterwards (tool calls, saving).
            db.commit()
            db.close()
            on_event({"type": "status", "message": "Asystent analizuje dane…"})
            outcome = _model_phase(
                action=action,
                prepared=prepared,
                llm=llm,
                registry=registry,
                tool_ctx=tool_ctx,
                db=db,
                trace=trace,
                seen=seen,
                on_event=on_event,
            )
        draft = outcome.draft
        if outcome.status in FALLBACK_STATUSES:
            trace.fallback(outcome.status, trace.now_ms())
            draft = action.fallback(prepared, params)
    except Exception as exc:
        log.exception("Action %s failed", action.id)
        db.rollback()
        outcome = _Outcome("error", error=type(exc).__name__)  # details only in the log
        trace.error(outcome.error or "", trace.now_ms())

    duration_ms = trace.now_ms()
    status = outcome.status
    source: Literal["ai", "rules", "none"] = (
        "ai" if status == "ok" else "rules" if status in FALLBACK_STATUSES else "none"
    )
    if draft is not None:
        report = _report(action, prepared, draft, seen, now)
    else:
        report = ActionReport(
            headline=prepared.no_data or FAILURE_MESSAGE, disclaimer=action.disclaimer
        )
    provider = trace.provider if trace.provider in PROVIDERS else None
    param_data = params.model_dump(mode="json")

    run = service.add_run(
        db,
        user_id=user_id,
        task=action.id,
        prompt_version=action.prompt_version,
        model=trace.model,
        provider=provider,
        status=status,
        params=param_data,
        steps=trace.steps,
        tool_calls=trace.tool_calls,
        messages=trace.messages,
        raw_outputs=trace.raw_outputs,
        validation_errors=trace.validation_errors,
        error=outcome.error,
        attempts=trace.llm_calls,
        llm_calls=trace.llm_calls,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        cost_usd=trace.cost_usd,
        duration_ms=duration_ms,
    )
    if reserved and (trace.input_tokens or trace.output_tokens):
        service.record_usage(
            db, user_id, now.date(), trace.input_tokens or 0, trace.output_tokens or 0
        )
    suggestion_id: int | None = None
    if source != "none":
        month = param_data.get("month")
        suggestion = service.add_suggestion(
            db,
            user_id=user_id,
            agent_run_id=run.id,
            type=action.id,
            month=month if isinstance(month, str) else None,
            summary=report.headline,
            report=report.model_dump(mode="json"),
            source=source,
            ai_status=status,
            params=param_data,
            provider=provider,
            risks=report.risks,
            sources=[s.model_dump(mode="json") for s in report.sources],
            disclaimer=report.disclaimer,
            model=trace.model or "rules",
            profile_snapshot=prepared.profile_snapshot,
            data_snapshot=prepared.snapshot,
            duration_ms=duration_ms,
        )
        suggestion_id = suggestion.id
    db.commit()
    run_id = run.id

    if status == "error":
        raise ActionFailed(FAILURE_MESSAGE)
    out = ActionRunOut(
        action=action.id,
        run_id=run_id,
        suggestion_id=suggestion_id,
        ai_status=status,  # type: ignore[arg-type]
        source=source,
        report=report,
        model=trace.model,
        provider=provider,
        duration_ms=duration_ms,
    )
    on_event({"type": "result", "data": out})
    return out
