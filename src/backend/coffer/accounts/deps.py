from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select

from coffer.accounts.models import AuthSession, User
from coffer.accounts.tokens import SESSION_COOKIE, hash_token
from coffer.core.db import DbSession


def get_current_user(request: Request, db: DbSession) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        user = db.scalar(
            select(User)
            .join(AuthSession, AuthSession.user_id == User.id)
            .where(
                AuthSession.token_hash == hash_token(token),
                AuthSession.expires_at > datetime.now(UTC),
            )
        )
        if user is not None:
            return user
    raise HTTPException(status_code=401, detail="Wymagane logowanie")


CurrentUser = Annotated[User, Depends(get_current_user)]
