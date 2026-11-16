import datetime as dt
import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from coffer.accounts.deps import CurrentUser
from coffer.agent import service
from coffer.agent.actions.base import Action
from coffer.agent.actions.catalog import ACTIONS, get_action
from coffer.agent.guard import ActionRateLimited
from coffer.agent.llm import LLMClient, get_llm_client, provider_name
from coffer.agent.runner import FAILURE_MESSAGE, ActionFailed, run_action
from coffer.agent.schemas import (
    ActionInfoOut,
    ActionRunOut,
    AgentRunListOut,
    AgentRunOut,
    AgentStatusOut,
    RunRequest,
    SuggestionListOut,
    SuggestionOut,
    ToolInfoOut,
)
from coffer.agent.sse import SSE_HEADERS, stream_events
from coffer.agent.tools.registry import default_registry
from coffer.core.db import DbSession, SessionFactory

router = APIRouter(prefix="/api/agent", tags=["agent"])

Day = dt.date | None


@router.get("/actions", response_model=list[ActionInfoOut])
def list_actions(user: CurrentUser) -> list[ActionInfoOut]:
    return [
        ActionInfoOut(
            id=a.id,
            name=a.name,
            description=a.description,
            params=list(a.params_ui),
            tools=list(a.tools),
            uses_user_data=a.uses_user_data,
            uses_internet=a.uses_internet,
        )
        for a in ACTIONS.values()
    ]


@router.get("/tools", response_model=list[ToolInfoOut])
def list_tools(user: CurrentUser) -> list[dict[str, Any]]:
    return default_registry().describe()


def _validated_params(action: Action, raw: dict[str, Any]) -> Any:
    try:
        return action.params_model.model_validate(raw)
    except ValidationError as exc:
        raise RequestValidationError(
            [{**e, "loc": ("body", "params", *e["loc"])} for e in json.loads(exc.json())]
        ) from exc


def _action_or_404(action_id: str) -> Action:
    action = get_action(action_id)
    if action is None:
        raise HTTPException(404, "Nie znaleziono akcji")
    return action


@router.post("/actions/{action_id}/run", response_model=ActionRunOut)
def run(
    action_id: str,
    body: RunRequest,
    request: Request,
    user: CurrentUser,
    db: DbSession,
    factory: SessionFactory,
    llm: Annotated[LLMClient | None, Depends(get_llm_client)],
) -> ActionRunOut | StreamingResponse:
    action = _action_or_404(action_id)
    params = _validated_params(action, body.params)
    user_id = user.id

    if "text/event-stream" in request.headers.get("accept", ""):

        def work(on_event: Any) -> None:
            try:
                with factory() as session:
                    run_action(session, user_id, action, params, llm, default_registry(), on_event)
            except ActionRateLimited as exc:
                on_event({"type": "error", "data": {"detail": str(exc)}})
            except Exception:  # ActionFailed or anything unexpected: the run is already recorded
                on_event({"type": "error", "data": {"detail": FAILURE_MESSAGE}})

        db.close()  # the stream outlives the request: do not hold a pooled connection for it
        return StreamingResponse(
            stream_events(work), media_type="text/event-stream", headers=SSE_HEADERS
        )
    try:
        return run_action(db, user_id, action, params, llm, default_registry())
    except ActionRateLimited as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": str(exc.retry_after)}) from exc
    except ActionFailed as exc:
        raise HTTPException(500, FAILURE_MESSAGE) from exc


@router.get("/suggestions", response_model=SuggestionListOut)
def list_suggestions(
    user: CurrentUser,
    db: DbSession,
    action: str | None = None,
    source: Literal["ai", "rules"] | None = None,
    date_from: Day = None,
    date_to: Day = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SuggestionListOut:
    filters = service.SuggestionFilters(
        action=action,
        source=source,
        date_from=date_from,
        date_to=date_to,
        q=q or None,
        order=order,
        limit=limit,
        offset=offset,
    )
    items, total = service.list_suggestions(db, user.id, filters)
    return SuggestionListOut(items=items, total=total)


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionOut)
def get_suggestion(suggestion_id: int, user: CurrentUser, db: DbSession) -> SuggestionOut:
    s = service.get_suggestion(db, user.id, suggestion_id)
    if s is None:
        raise HTTPException(404, "Nie znaleziono sugestii")
    return s


@router.get("/runs", response_model=AgentRunListOut)
def list_runs(
    user: CurrentUser,
    db: DbSession,
    action: str | None = None,
    status: str | None = None,
    provider: str | None = None,
    date_from: Day = None,
    date_to: Day = None,
    sort: Literal["created_at", "duration_ms", "cost_usd", "tokens"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AgentRunListOut:
    filters = service.RunFilters(
        action=action,
        status=status,
        provider=provider,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )
    items, total = service.list_runs(db, user.id, filters)
    return AgentRunListOut(items=items, total=total)


@router.get("/runs/{run_id}", response_model=AgentRunOut)
def get_run(run_id: int, user: CurrentUser, db: DbSession) -> AgentRunOut:
    r = service.get_run(db, user.id, run_id)
    if r is None:
        raise HTTPException(404, "Nie znaleziono przebiegu agenta")
    return r


@router.get("/status", response_model=AgentStatusOut)
def status(
    user: CurrentUser,
    llm: Annotated[LLMClient | None, Depends(get_llm_client)],
) -> AgentStatusOut:
    # Never probed at startup: the first status request after a Render cold start pays for the
    # (cached, ~2 s timeout) probe instead of the boot.
    if llm is None:
        return AgentStatusOut(provider="none", model=None, available=False)
    try:
        st = llm.status()
    except Exception:
        return AgentStatusOut(provider=provider_name(llm), model=None, available=False)
    # Read after status(): a fallback chain reports the provider of its active (first available)
    # model.
    return AgentStatusOut(provider=provider_name(llm), model=st.model, available=st.available)
