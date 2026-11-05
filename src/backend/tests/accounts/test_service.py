import string

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from coffer.accounts import service
from coffer.accounts.models import AuthSession, User
from coffer.accounts.tokens import hash_token


def test_hash_password_is_argon2_and_salted() -> None:
    h1 = service.hash_password("haslo12345")
    h2 = service.hash_password("haslo12345")
    assert h1.startswith("$argon2")
    assert "haslo12345" not in h1
    assert h1 != h2


def test_verify_password() -> None:
    h = service.hash_password("haslo12345")
    assert service.verify_password(h, "haslo12345") is True
    assert service.verify_password(h, "Haslo12345") is False
    assert service.verify_password(h, "") is False


def test_verify_password_garbage_hash_is_false() -> None:
    assert service.verify_password("to-nie-jest-hash", "haslo12345") is False


@settings(
    max_examples=15, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(pw=st.text(alphabet=string.printable.strip() + "żółćąęńśźŻ", min_size=8, max_size=128))
def test_hash_roundtrip_property(pw: str) -> None:
    h = service.hash_password(pw)
    assert service.verify_password(h, pw)
    assert not service.verify_password(h, pw + "x")


def test_register_creates_user(db: Session) -> None:
    user = service.register(db, "jan@example.com", "haslo12345")
    assert user.id is not None
    stored = db.scalars(select(User)).one()
    assert stored.email == "jan@example.com"
    assert stored.password_hash.startswith("$argon2")
    assert stored.password_hash != "haslo12345"


def test_register_duplicate_raises_email_taken(db: Session) -> None:
    service.register(db, "jan@example.com", "haslo12345")
    with pytest.raises(service.EmailTaken):
        service.register(db, "jan@example.com", "innehaslo123")
    assert len(db.scalars(select(User)).all()) == 1


def test_authenticate(db: Session) -> None:
    created = service.register(db, "jan@example.com", "haslo12345")
    ok = service.authenticate(db, "jan@example.com", "haslo12345")
    assert ok is not None and ok.id == created.id
    assert service.authenticate(db, "jan@example.com", "zle") is None
    assert service.authenticate(db, "nikt@example.com", "haslo12345") is None


def test_create_session_stores_only_hash(db: Session) -> None:
    user = service.register(db, "jan@example.com", "haslo12345")
    token = service.create_session(db, user)
    assert len(token) >= 32
    row = db.scalars(select(AuthSession)).one()
    assert row.user_id == user.id
    assert row.token_hash == hash_token(token)
    assert token not in row.token_hash


def test_create_session_tokens_unique(db: Session) -> None:
    user = service.register(db, "jan@example.com", "haslo12345")
    assert service.create_session(db, user) != service.create_session(db, user)


def test_delete_session(db: Session) -> None:
    user = service.register(db, "jan@example.com", "haslo12345")
    keep = service.create_session(db, user)
    drop = service.create_session(db, user)
    service.delete_session(db, drop)
    rows = db.scalars(select(AuthSession)).all()
    assert [r.token_hash for r in rows] == [hash_token(keep)]


def test_delete_session_unknown_token_is_noop(db: Session) -> None:
    service.delete_session(db, "nieistniejacy")
