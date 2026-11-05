from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from coffer.accounts.deps import CurrentUser
from coffer.agent import service
from coffer.agent.llm import LLMClient, get_llm_client, provider_name
from coffer.agent.schemas import (
    AgentRunListItem,
    AgentRunOut,
    AgentStatusOut,
    SuggestionOut,
    SurplusRequest,
    SurplusSuggestionOut,
)
from coffer.agent.sse import SSE_HEADERS, stream_events
from coffer.agent.tools.registry import default_registry
from coffer.agent.workflows.surplus import run_surplus
from coffer.core.db import DbSession, SessionFactory

router = APIRouter(prefix="/api/agent", tags=["agent"])

Limit = Annotated[int, Query(ge=1, le=100)]


@router.post("/surplus", response_model=SurplusSuggestionOut)
def surplus(
    body: SurplusRequest,
    user: CurrentUser,
    db: DbSession,
    llm: Annotated[LLMClient | None, Depends(get_llm_client)],
) -> SurplusSuggestionOut:
    return run_surplus(db, user.id, body.month, llm, default_registry())


@router.post("/surplus/stream")
def surplus_stream(
    body: SurplusRequest,
    user: CurrentUser,
    factory: SessionFactory,
    llm: Annotated[LLMClient | None, Depends(get_llm_client)],
) -> StreamingResponse:
    user_id, month = user.id, body.month

    def work(on_event: Any) -> None:
        seen: dict[str, Any] = {}

        def relay(event: dict[str, Any]) -> None:
            seen[event["type"]] = event
            on_event(event)

        try:
            with factory() as session:
                run_surplus(session, user_id, month, llm, default_registry(), relay)
        except Exception:
            if "result" in seen:
                return
            if "summary" in seen:
                out = SurplusSuggestionOut(summary=seen["summary"]["data"], ai_status="unavailable")
                on_event({"type": "result", "data": out})
            else:
                on_event({"type": "error", "data": {"detail": "Nie udało się wykonać analizy"}})

    return StreamingResponse(
        stream_events(work), media_type="text/event-stream", headers=SSE_HEADERS
    )


@router.get("/suggestions", response_model=list[SuggestionOut])
def list_suggestions(user: CurrentUser, db: DbSession, limit: Limit = 20) -> list[SuggestionOut]:
    return [service.suggestion_out(s) for s in service.list_suggestions(db, user.id, limit)]


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionOut)
def get_suggestion(suggestion_id: int, user: CurrentUser, db: DbSession) -> SuggestionOut:
    s = service.get_suggestion(db, user.id, suggestion_id)
    if s is None:
        raise HTTPException(404, "Nie znaleziono sugestii")
    return service.suggestion_out(s)


@router.get("/runs", response_model=list[AgentRunListItem])
def list_runs(user: CurrentUser, db: DbSession, limit: Limit = 20) -> list[AgentRunListItem]:
    return [
        AgentRunListItem.model_validate(r, from_attributes=True)
        for r in service.list_runs(db, user.id, limit)
    ]


@router.get("/runs/{run_id}", response_model=AgentRunOut)
def get_run(run_id: int, user: CurrentUser, db: DbSession) -> AgentRunOut:
    r = service.get_run(db, user.id, run_id)
    if r is None:
        raise HTTPException(404, "Nie znaleziono przebiegu agenta")
    return AgentRunOut.model_validate(r, from_attributes=True)


@router.get("/status", response_model=AgentStatusOut)
def status(
    user: CurrentUser,
    llm: Annotated[LLMClient | None, Depends(get_llm_client)],
) -> AgentStatusOut:
    provider = provider_name(llm)
    if llm is None:
        return AgentStatusOut(provider=provider, model=None, available=False)
    try:
        st = llm.status()
    except Exception:
        return AgentStatusOut(provider=provider, model=None, available=False)
    return AgentStatusOut(provider=provider, model=st.model, available=st.available)
