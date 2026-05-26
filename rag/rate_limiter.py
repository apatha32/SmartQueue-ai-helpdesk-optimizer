from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded


def _get_session_key(request: Request) -> str:
    """Rate-limit per session_id header, falling back to client IP."""
    return request.headers.get("X-Session-ID") or request.client.host or "unknown"


limiter = Limiter(key_func=_get_session_key)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}. Slow down."},
    )
