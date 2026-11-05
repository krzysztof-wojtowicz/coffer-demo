from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from coffer.core.config import get_settings

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class OriginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        origin = request.headers.get("origin")
        if (
            request.method in UNSAFE_METHODS
            and origin is not None
            and origin not in get_settings().allowed_origins
        ):
            return JSONResponse({"detail": "Niedozwolone źródło żądania"}, status_code=403)
        return await call_next(request)
