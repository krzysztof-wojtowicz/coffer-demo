from sqlalchemy.orm import Session

from coffer.profile.models import InvestmentProfile
from coffer.profile.schemas import ProfileIn


def get(db: Session, user_id: int) -> InvestmentProfile | None:
    return db.get(InvestmentProfile, user_id)


def upsert(db: Session, user_id: int, data: ProfileIn) -> InvestmentProfile:
    profile = db.get(InvestmentProfile, user_id)
    if profile is None:
        profile = InvestmentProfile(user_id=user_id)
        db.add(profile)
    profile.horizon = data.horizon
    profile.risk = data.risk
    profile.preferred_classes = list(data.preferred_classes)
    db.commit()
    db.refresh(profile)
    return profile
