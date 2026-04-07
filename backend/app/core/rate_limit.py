import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter for auth endpoints."""

    def __init__(self, app, rate_limit: int = 10, window: int = 60):
        super().__init__(app)
        self.rate_limit = rate_limit  # max requests per window
        self.window = window  # window in seconds
        self.requests: dict[str, list[float]] = defaultdict(list)
        # Paths to rate limit
        self.limited_paths = {
            "/api/v1/auth/login",
            "/api/v1/auth/demo-login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/portal/auth/login",
            "/api/v1/setup/initialize",
        }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "POST" and path in self.limited_paths:
            client_ip = request.client.host if request.client else "unknown"
            key = f"{client_ip}:{path}"
            now = time.time()

            # Clean old entries
            self.requests[key] = [t for t in self.requests[key] if now - t < self.window]

            if len(self.requests[key]) >= self.rate_limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please try again later."},
                )

            self.requests[key].append(now)

        return await call_next(request)
