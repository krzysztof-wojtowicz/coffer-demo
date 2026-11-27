from dataclasses import asdict

from fastapi import APIRouter

from coffer.accounts.deps import CurrentUser
from coffer.core.db import DbSession
from coffer.profile import service
from coffer.profile.models import InvestmentProfile
from coffer.profile.schemas import ProfileIn, ProfileOut

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _out(profile: InvestmentProfile) -> ProfileOut:
    return ProfileOut.model_validate(
        {
            "horizon": profile.horizon,
            "risk": profile.risk,
            "preferred_classes": profile.preferred_classes,
            "updated_at": profile.updated_at,
            "target": [asdict(t) for t in service.target(profile)],
        }
    )


@router.get("", response_model=ProfileOut | None)
def get_profile(user: CurrentUser, db: DbSession) -> ProfileOut | None:
    profile = service.get(db, user.id)
    return _out(profile) if profile else None


@router.put("", response_model=ProfileOut)
def put_profile(data: ProfileIn, user: CurrentUser, db: DbSession) -> ProfileOut:
    return _out(service.upsert(db, user.id, data))
