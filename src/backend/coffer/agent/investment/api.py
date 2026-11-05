from typing import Annotated

from fastapi import APIRouter, Depends

from coffer.accounts.deps import CurrentUser
from coffer.agent.investment.advisor import RiskProfile, advise, to_risk_profile
from coffer.agent.investment.schemas import AdviceOut, AdviceRequest
from coffer.agent.llm import LLMClient, get_llm_client
from coffer.core.db import DbSession
from coffer.profile import service as profile_service

router = APIRouter(prefix="/api/agent/investment", tags=["agent"])


@router.post("/advice", response_model=AdviceOut)
def advice(
    body: AdviceRequest,
    user: CurrentUser,
    db: DbSession,
    llm: Annotated[LLMClient | None, Depends(get_llm_client)],
) -> AdviceOut:
    profile = profile_service.get(db, user.id)
    risk_profile = (
        to_risk_profile(profile.risk, profile.horizon, profile.preferred_classes)
        if profile is not None
        else RiskProfile()
    )
    return advise(body.holdings, risk_profile, llm)
