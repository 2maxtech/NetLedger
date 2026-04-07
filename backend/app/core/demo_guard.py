"""Middleware that blocks mutating requests for demo users.

Demo users (is_demo=True in JWT) can only read data. Any POST/PUT/PATCH/DELETE
request is rejected with 403, except for auth endpoints (login, refresh, etc.).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.security import decode_token

# Methods that mutate data
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Path prefixes that demo users ARE allowed to call with any method
_ALLOWED_PREFIXES = (
    "/api/v1/auth/",
    "/api/v1/portal/auth/",
)


class DemoGuardMiddleware(BaseHTTPMiddleware):
    """Return 403 for mutating requests when the JWT carries is_demo=True."""

    async def dispatch(self, request: Request, call_next):
        if request.method not in _MUTATING_METHODS:
            return await call_next(request)

        path = request.url.path

        # Always allow auth-related endpoints (login, refresh, demo-login, etc.)
        if any(path.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
            return await call_next(request)

        # Check for demo flag in the JWT
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = decode_token(token)
            if payload and payload.get("is_demo"):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Demo mode \u2014 sign up for full access"},
                )

        return await call_next(request)
