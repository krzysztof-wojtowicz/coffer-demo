from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from coffer.accounts import ratelimit, service
from coffer.accounts.deps import CurrentUser
from coffer.accounts.models import User
from coffer.accounts.policy import MAX_LENGTH
from coffer.accounts.schemas import Credentials, PasswordChange, PasswordConfirm, UserOut
from coffer.accounts.tokens import SESSION_COOKIE
from coffer.core.config import get_settings
from coffer.core.db import DbSession

router = APIRouter(prefix="/api/auth", tags=["auth"])

_WRONG_PASSWORD = "Nieprawidłowe hasło"


def _set_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_days * 86400,
        path="/",
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
    )


def _clear_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
    )


async def redacted_validation_handler(request: Request, exc: Exception) -> Response:
    """422 for /api/auth/*: pydantic errors carry the offending `input` (a password, or the
    whole body when a field is missing), so drop it and give a Polish `msg`."""
    assert isinstance(exc, RequestValidationError)
    if not request.url.path.startswith("/api/auth/"):
        return await request_validation_exception_handler(request, exc)
    errors = [
        {
            "type": err.get("type", ""),
            "loc": list(err.get("loc", ())),
            "msg": "Pole jest wymagane"
            if "missing" in str(err.get("type", ""))
            else "Niepoprawna wartość",
        }
        for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email)


def _weak(exc: service.WeakPassword) -> HTTPException:
    return HTTPException(status_code=422, detail=" ".join(exc.problems))


def _email_key(email: str) -> str:
    return f"login:email:{email}"


def _check_lengths(*passwords: str) -> None:
    """Length cap checked here, not in the schema: a pydantic 422 would echo the password
    back in its `input` field (and in English)."""
    if any(len(p) > MAX_LENGTH for p in passwords):
        raise HTTPException(
            status_code=422, detail=f"Hasło może mieć najwyżej {MAX_LENGTH} znaków."
        )


def _reserve_account_attempt(user: User) -> str:
    """Wrong-password confirmations count like failed logins (per account). The attempt is
    reserved atomically before the password is verified; release it if it was right."""
    key = _email_key(user.email)
    ratelimit.reserve((key, ratelimit.LOGIN_FAILS_PER_EMAIL))
    return key


@router.post("/register", status_code=201, responses={409: {}, 422: {}, 429: {}})
def register(body: Credentials, request: Request, response: Response, db: DbSession) -> UserOut:
    _check_lengths(body.password)
    # Counts every attempt (weak password and taken e-mail included).
    ratelimit.reserve((f"register:ip:{ratelimit.client_ip(request)}", ratelimit.REGISTER_PER_IP))
    try:
        service.check_password_policy(body.password, body.email)
        user = service.register(db, body.email, body.password)
    except service.WeakPassword as exc:
        raise _weak(exc) from None
    except service.EmailTaken:
        # UC-01 5a requires telling the user the address is taken (and proposing login).
        raise HTTPException(
            status_code=409, detail="Konto z tym adresem e-mail już istnieje"
        ) from None
    _set_cookie(response, service.create_session(db, user))
    return _user_out(user)


@router.post("/login", responses={401: {}, 429: {}})
def login(body: Credentials, request: Request, response: Response, db: DbSession) -> UserOut:
    _check_lengths(body.password)
    email_key = _email_key(body.email)
    ip_key = f"login:ip:{ratelimit.client_ip(request)}"
    # Reserve the attempt as a failure up front (atomic check + count), then undo on success.
    ratelimit.reserve(
        (email_key, ratelimit.LOGIN_FAILS_PER_EMAIL), (ip_key, ratelimit.LOGIN_FAILS_PER_IP)
    )
    user = service.authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Nieprawidłowy e-mail lub hasło")
    # Success clears the e-mail counter; earlier failures from this IP stay counted.
    ratelimit.limiter.reset(email_key)
    ratelimit.limiter.release(ip_key)
    # Rotation: a session cookie the browser already had is revoked, never reused.
    old_token = request.cookies.get(SESSION_COOKIE)
    if old_token:
        service.delete_session(db, old_token)
    _set_cookie(response, service.create_session(db, user))
    return _user_out(user)


@router.post("/logout", status_code=204)
def logout(request: Request, db: DbSession) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        service.delete_session(db, token)
    response = Response(status_code=204)
    _clear_cookie(response)
    return response


@router.post("/logout-all", status_code=204)
def logout_all(user: CurrentUser, db: DbSession) -> Response:
    service.delete_all_sessions(db, user)
    response = Response(status_code=204)
    _clear_cookie(response)
    return response


@router.post("/password", status_code=204, responses={403: {}, 422: {}, 429: {}})
def change_password(body: PasswordChange, user: CurrentUser, db: DbSession) -> Response:
    _check_lengths(body.current_password, body.new_password)
    key = _reserve_account_attempt(user)
    try:
        token = service.change_password(db, user, body.current_password, body.new_password)
    except service.WrongPassword:
        raise HTTPException(status_code=403, detail=_WRONG_PASSWORD) from None
    except service.WeakPassword as exc:
        ratelimit.limiter.release(key)
        raise _weak(exc) from None
    ratelimit.limiter.release(key)
    response = Response(status_code=204)
    _set_cookie(response, token)
    return response


@router.delete("/account", status_code=204, responses={403: {}, 429: {}})
def delete_account(body: PasswordConfirm, user: CurrentUser, db: DbSession) -> Response:
    _check_lengths(body.password)
    key = _reserve_account_attempt(user)
    try:
        service.delete_account(db, user, body.password)
    except service.WrongPassword:
        raise HTTPException(status_code=403, detail=_WRONG_PASSWORD) from None
    ratelimit.limiter.release(key)
    response = Response(status_code=204)
    _clear_cookie(response)
    return response


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return _user_out(user)
