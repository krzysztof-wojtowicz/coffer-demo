import json
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from coffer.agent import service
from coffer.agent.drafts import SuggestionDraft
from coffer.agent.llm import LLMClient, LLMMessage, LLMUnavailable
from coffer.agent.models import AgentRun, Suggestion
from coffer.agent.schemas import DISCLAIMER, SurplusSuggestionOut
from coffer.agent.tools.registry import ToolCall, ToolContext, ToolRegistry
from coffer.agent.validator import validate
from coffer.budget import service as budget_service
from coffer.budget.schemas import MonthSummaryOut
from coffer.core.config import get_settings

PROMPT_VERSION = "surplus_v2"
PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / f"{PROMPT_VERSION}.md").read_text(
    encoding="utf-8"
)

AgentEvent = dict[str, Any]


def noop(event: AgentEvent) -> None:
    return None


def _validation_message(errors: list[str]) -> str:
    return (
        "Odpowiedź nie przeszła walidacji: "
        + "; ".join(errors)
        + ". Popraw ją i odpowiedz ponownie w tym samym formacie JSON."
    )


def run_surplus(
    db: Session,
    user_id: int,
    month: str,
    llm: LLMClient | None,
    registry: ToolRegistry,
    on_event: Callable[[AgentEvent], None] = noop,
) -> SurplusSuggestionOut:
    settings = get_settings()
    started = time.perf_counter()
    ctx = ToolContext(db=db, user_id=user_id)
    tool_calls: list[ToolCall] = []
    messages: list[dict[str, str]] = []
    raw_outputs: list[str] = []
    validation_errors: list[str] = []
    attempts = 0
    model: str | None = None
    error: str | None = None
    in_tokens: int | None = None
    out_tokens: int | None = None

    def finish(
        status: str,
        summary_out: MonthSummaryOut,
        draft: SuggestionDraft | None = None,
    ) -> SurplusSuggestionOut:
        duration_ms = int((time.perf_counter() - started) * 1000)
        run = AgentRun(
            user_id=user_id,
            task="surplus",
            prompt_version=PROMPT_VERSION,
            model=model,
            status=status,
            tool_calls=[asdict(c) for c in tool_calls],
            messages=messages,
            raw_outputs=raw_outputs,
            validation_errors=validation_errors,
            error=error,
            attempts=attempts,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            duration_ms=duration_ms,
        )
        db.add(run)
        db.flush()
        suggestion_out = None
        if status == "ok" and draft is not None:
            analysis = next(c for c in tool_calls if c.name == "get_month_analysis")
            profile = next((c for c in tool_calls if c.name == "get_investment_profile"), None)
            profile_snapshot = (
                profile.output if profile is not None and profile.output.get("available") else None
            )
            suggestion = Suggestion(
                user_id=user_id,
                agent_run_id=run.id,
                type="surplus",
                month=month,
                summary=draft.summary,
                rationale=[r.model_dump() for r in draft.rationale],
                risks=draft.risks,
                sources=[],
                disclaimer=DISCLAIMER,
                model=model or "unknown",
                profile_snapshot=profile_snapshot,
                data_snapshot=analysis.output,
                duration_ms=duration_ms,
            )
            db.add(suggestion)
            db.flush()
            db.refresh(suggestion)
            suggestion_out = service.suggestion_out(suggestion)
        db.commit()
        ai_status = {
            "ok": "ok",
            "no_surplus": "no_surplus",
            "limited": "limited",
        }.get(status, "unavailable")
        out = SurplusSuggestionOut(
            summary=summary_out,
            ai_status=ai_status,  # type: ignore[arg-type]
            suggestion=suggestion_out,
            run_id=run.id,
        )
        on_event({"type": "result", "data": out})
        return out

    on_event({"type": "status", "message": "Liczę podsumowanie miesiąca…"})
    tool_calls.append(registry.call("get_month_analysis", {"month": month}, ctx))
    summary = budget_service.month_summary(db, user_id, month)
    summary_out = MonthSummaryOut.from_summary(summary)
    on_event({"type": "summary", "data": summary_out})

    if summary.surplus == 0:
        return finish("no_surplus", summary_out)
    if llm is None:
        return finish("unavailable", summary_out)
    if service.count_runs_today(db, user_id) >= settings.agent_daily_limit:
        return finish("limited", summary_out)

    on_event({"type": "status", "message": "Sprawdzam profil inwestycyjny…"})
    tool_calls.append(registry.call("get_investment_profile", {}, ctx))

    # The LLM call can take tens of seconds; return the connection to the pool first (N08).
    # The same session is reused afterwards for saving.
    db.commit()
    db.close()

    on_event({"type": "status", "message": "Asystent analizuje dane…"})
    intro = "Oto wyniki narzędzi dla wybranego miesiąca. Zaproponuj, jak wykorzystać nadwyżkę.\n"
    payload = [{"tool": c.name, "output": c.output} for c in tool_calls]
    conversation = [LLMMessage("user", intro + json.dumps(payload, ensure_ascii=False))]
    messages.append({"role": "system", "content": PROMPT})
    messages.append({"role": "user", "content": conversation[0].content})

    draft: SuggestionDraft | None = None
    status = "invalid"
    schema = SuggestionDraft.model_json_schema()
    while attempts < settings.agent_max_attempts:
        attempts += 1
        try:
            response = llm.complete(system=PROMPT, messages=conversation, response_schema=schema)
        except LLMUnavailable as exc:
            status, error = "unavailable", str(exc)
            break
        model = response.model
        if response.input_tokens is not None:
            in_tokens = (in_tokens or 0) + response.input_tokens
        if response.output_tokens is not None:
            out_tokens = (out_tokens or 0) + response.output_tokens
        raw_outputs.append(response.content)
        messages.append({"role": "assistant", "content": response.content})

        errors: list[str]
        parsed: SuggestionDraft | None = None
        try:
            parsed = SuggestionDraft.model_validate_json(response.content)
            errors = validate(parsed, tool_calls)
        except ValidationError as exc:
            errors = [
                f"Niepoprawny format odpowiedzi ({'.'.join(str(p) for p in e['loc'])}: {e['msg']})"
                for e in exc.errors()
            ]
        if not errors:
            draft, status = parsed, "ok"
            break
        validation_errors.extend(errors)
        if attempts < settings.agent_max_attempts:
            on_event({"type": "status", "message": "Poprawiam odpowiedź…"})
            conversation.append(LLMMessage("assistant", response.content))
            msg = LLMMessage("user", _validation_message(errors))
            conversation.append(msg)
            messages.append({"role": "user", "content": msg.content})

    return finish(status, summary_out, draft)
