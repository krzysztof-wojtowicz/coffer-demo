from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from coffer.accounts.models import AuthSession, User
from coffer.accounts.tokens import hash_token, new_token
from coffer.core.config import get_settings

_hasher = PasswordHasher()
# Used to equalize timing when the e-mail is unknown.
_DUMMY_HASH = _hasher.hash("coffer-dummy-password")


class EmailTaken(Exception):
    pass


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(hash: str, password: str) -> bool:
    try:
        return _hasher.verify(hash, password)
    except (VerificationError, InvalidHashError):
        return False


def register(db: Session, email: str, password: str) -> User:
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise EmailTaken
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise EmailTaken from None
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(_DUMMY_HASH, password)
        return None
    return user if verify_password(user.password_hash, password) else None


def create_session(db: Session, user: User) -> str:
    token = new_token()
    expires_at = datetime.now(UTC) + timedelta(days=get_settings().session_ttl_days)
    db.add(AuthSession(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at))
    db.commit()
    return token


def delete_session(db: Session, token: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    db.commit()
