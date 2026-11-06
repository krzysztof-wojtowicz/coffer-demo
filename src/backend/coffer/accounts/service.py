import threading
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from coffer.accounts.models import AuthSession, User
from coffer.accounts.policy import password_problems
from coffer.accounts.tokens import hash_token, new_token
from coffer.core.config import get_settings

# Argon2id with the OWASP minimum (m=19 MiB, t=2, p=1) instead of argon2-cffi's default
# RFC 9106 "low memory" profile (m=64 MiB, t=3, p=4): the API runs on Render free (512 MB RAM,
# shared CPU), where 64 MiB per hash would let a few parallel logins exhaust memory.
# Changing these values is safe: old hashes still verify and are upgraded on the next login.
_hasher = PasswordHasher(
    time_cost=2, memory_cost=19 * 1024, parallelism=1, hash_len=32, salt_len=16, type=Type.ID
)
# Sync endpoints run in a thread pool (up to 40 threads); cap concurrent hashes so that
# memory stays bounded under a burst of logins. Until rehashed on login, legacy hashes use
# argon2-cffi defaults (64 MiB, p=4), so the default of 2 slots keeps the worst case ~128 MiB
# on Render's 512 MB (COFFER_PASSWORD_HASH_CONCURRENCY).
HASH_CONCURRENCY = get_settings().password_hash_concurrency
_hash_slots = threading.BoundedSemaphore(HASH_CONCURRENCY)
# Used to equalize timing when the e-mail is unknown.
_DUMMY_HASH = _hasher.hash("coffer-dummy-password")


class EmailTaken(Exception):
    pass


class WrongPassword(Exception):
    pass


class WeakPassword(Exception):
    def __init__(self, problems: list[str]) -> None:
        super().__init__(" ".join(problems))
        self.problems = problems


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    with _hash_slots:
        return _hasher.hash(password)


def verify_password(hash: str, password: str) -> bool:
    try:
        with _hash_slots:
            return _hasher.verify(hash, password)
    except (VerificationError, InvalidHashError):
        return False


def check_password_policy(password: str, email: str) -> None:
    problems = password_problems(password, email)
    if problems:
        raise WeakPassword(problems)


def _find_user(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == normalize_email(email)))


def register(db: Session, email: str, password: str) -> User:
    """Create an account. The password policy is enforced by the API (check_password_policy)."""
    email = normalize_email(email)
    if _find_user(db, email) is not None:
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
    user = _find_user(db, email)
    if user is None:
        verify_password(_DUMMY_HASH, password)
        return None
    if not verify_password(user.password_hash, password):
        return None
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = datetime.now(UTC)
    db.commit()
    return user


def create_session(db: Session, user: User) -> str:
    now = datetime.now(UTC)
    # Opportunistic cleanup: expired sessions are useless (deps.py ignores them).
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    token = new_token()
    expires_at = now + timedelta(days=get_settings().session_ttl_days)
    db.add(AuthSession(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at))
    db.commit()
    return token


def delete_session(db: Session, token: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    db.commit()


def delete_all_sessions(db: Session, user: User) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.commit()


def change_password(db: Session, user: User, current: str, new: str) -> str:
    """Set a new password, revoke every session and return a fresh session token."""
    if not verify_password(user.password_hash, current):
        raise WrongPassword
    problems = password_problems(new, user.email)
    if new == current:
        problems.append("Nowe hasło musi różnić się od obecnego.")
    if problems:
        raise WeakPassword(problems)
    user.password_hash = hash_password(new)
    user.password_changed_at = datetime.now(UTC)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.commit()
    return create_session(db, user)


def delete_account(db: Session, user: User, password: str) -> None:
    """Delete the user; ON DELETE CASCADE removes sessions and all financial data (UC-08)."""
    if not verify_password(user.password_hash, password):
        raise WrongPassword
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
