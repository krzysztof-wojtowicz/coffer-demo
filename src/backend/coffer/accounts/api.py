from fastapi import APIRouter, HTTPException, Request, Response

from coffer.accounts import service
from coffer.accounts.deps import CurrentUser
from coffer.accounts.models import User
from coffer.accounts.schemas import Credentials, UserOut
from coffer.accounts.tokens import SESSION_COOKIE
from coffer.core.config import get_settings
from coffer.core.db import DbSession

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_days * 86400,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email)


@router.post("/register", status_code=201)
def register(body: Credentials, response: Response, db: DbSession) -> UserOut:
    try:
        user = service.register(db, body.email, body.password)
    except service.EmailTaken:
        raise HTTPException(
            status_code=409, detail="Konto z tym adresem e-mail już istnieje"
        ) from None
    _set_cookie(response, service.create_session(db, user))
    return _user_out(user)


@router.post("/login")
def login(body: Credentials, response: Response, db: DbSession) -> UserOut:
    user = service.authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Nieprawidłowy e-mail lub hasło")
    _set_cookie(response, service.create_session(db, user))
    return _user_out(user)


@router.post("/logout", status_code=204)
def logout(request: Request, db: DbSession) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        service.delete_session(db, token)
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return _user_out(user)
