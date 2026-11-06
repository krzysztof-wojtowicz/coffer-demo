import re
from functools import lru_cache

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from coffer.core.config import Settings, get_settings

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CORS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]
# Accept (incl. text/event-stream for SSE) is CORS-safelisted; JSON bodies need Content-Type.
CORS_HEADERS = ["Content-Type"]
CORS_MAX_AGE_S = 600


@lru_cache
def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def is_allowed_origin(origin: str, settings: Settings) -> bool:
    """The one origin policy shared by the CSRF Origin check and CORS."""
    if origin in settings.allowed_origins:
        return True
    regex = settings.allowed_origin_regex
    return regex is not None and _compile(regex).fullmatch(origin) is not None


class OriginMiddleware(BaseHTTPMiddleware):
    """CSRF defence: state-changing requests carrying a foreign Origin get 403.

    Requests without Origin (curl, same-origin GET) and safe methods (incl. OPTIONS) pass.
    """

    def __init__(self, app: ASGIApp, settings: Settings | None = None) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = self._settings or get_settings()
        origin = request.headers.get("origin")
        if (
            request.method in UNSAFE_METHODS
            and origin is not None
            and not is_allowed_origin(origin, settings)
        ):
            return JSONResponse({"detail": "Niedozwolone źródło żądania"}, status_code=403)
        return await call_next(request)


class _CofferCORSMiddleware(CORSMiddleware):
    """Starlette CORS that delegates the origin decision to `is_allowed_origin`."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(
            app,
            allow_origins=settings.allowed_origins,  # never "*": config validation rejects it
            allow_origin_regex=settings.allowed_origin_regex,
            allow_credentials=True,
            allow_methods=CORS_METHODS,
            allow_headers=CORS_HEADERS,
            max_age=CORS_MAX_AGE_S,
        )
        self._settings = settings

    def is_allowed_origin(self, origin: str) -> bool:
        return is_allowed_origin(origin, self._settings)


def install_origin_policy(app: FastAPI, settings: Settings) -> None:
    """Origin check always; CORS only when enabled.

    add_middleware prepends, so CORS (added last) is the outermost layer: it answers preflight
    OPTIONS before the Origin check and before any auth dependency (no 401/403 on preflight),
    and it decorates every response, including 401/403/422 errors and streamed SSE.
    """
    app.add_middleware(OriginMiddleware, settings=settings)
    if settings.cors_enabled:
        app.add_middleware(_CofferCORSMiddleware, settings=settings)
