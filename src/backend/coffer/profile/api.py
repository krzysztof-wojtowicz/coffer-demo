from fastapi import APIRouter

from coffer.accounts.deps import CurrentUser
from coffer.core.db import DbSession
from coffer.profile import service
from coffer.profile.schemas import ProfileIn, ProfileOut

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileOut | None)
def get_profile(user: CurrentUser, db: DbSession) -> ProfileOut | None:
    profile = service.get(db, user.id)
    return ProfileOut.model_validate(profile) if profile else None


@router.put("", response_model=ProfileOut)
def put_profile(data: ProfileIn, user: CurrentUser, db: DbSession) -> ProfileOut:
    return ProfileOut.model_validate(service.upsert(db, user.id, data))
