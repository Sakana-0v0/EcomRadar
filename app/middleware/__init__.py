"""FastAPI 多租户中间件 + 限流中间件.

TenantMiddleware:
- 解析 X-Tenant-ID Header (SSE EventSource 场景回退到 query param)
- 缺失/空 -> 拒绝 (400)
- 注入到 request.state.tenant_id

RateLimitMiddleware:
- 基于 tenant_id 调用 SlidingWindowRateLimiter
- 超出限额返回 429 Too Many Requests
- 在响应头添加 X-RateLimit-* 提示
"""
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

from app.services.security.rate_limiter import (
    SlidingWindowRateLimiter,
    RateLimiterBackend,
    InMemoryRateLimiter,
)


_EXEMPT_PATHS = frozenset({
    "/",
    "/api/v1/health",
    "/api/v1/meta",
    "/docs",
    "/redoc",
    "/openapi.json",
})


class TenantMiddleware(BaseHTTPMiddleware):
    """多租户解析中间件.

    要求:
    - X-Tenant-ID Header 必须存在且非空
    - 可选: X-User-ID Header 记录当前用户
    """

    EXEMPT_PATHS = _EXEMPT_PATHS

    def __init__(self, app: ASGIApp, required: bool = True):
        super().__init__(app)
        self.required = required

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in self.EXEMPT_PATHS or path.startswith("/assets/"):
            request.state.tenant_id = "anonymous"
            request.state.user_id = None
            return await call_next(request)

        tenant_id = request.headers.get("X-Tenant-ID", "").strip()
        if not tenant_id:
            # EventSource (SSE) 不支持自定义 header, 降级从 query param 读取
            tenant_id = request.query_params.get("tenant_id", "").strip()
        if not tenant_id:
            if self.required:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "X-Tenant-ID header is required"},
                )
            tenant_id = "anonymous"

        user_id = request.headers.get("X-User-ID", "").strip() or None

        if not tenant_id.replace("-", "").replace("_", "").isalnum():
            return JSONResponse(
                status_code=400,
                content={"detail": "X-Tenant-ID must be alphanumeric"},
            )

        request.state.tenant_id = tenant_id
        request.state.user_id = user_id
        response = await call_next(request)
        response.headers["X-Tenant-ID"] = tenant_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件 (基于 tenant_id).

    需要 TenantMiddleware 在前.
    """

    EXEMPT_PATHS = _EXEMPT_PATHS

    def __init__(
        self,
        app: ASGIApp,
        limiter: Optional[RateLimiterBackend] = None,
        limit: int = 10,
        window_seconds: float = 60.0,
    ):
        super().__init__(app)
        self.limiter = limiter or InMemoryRateLimiter(limit=limit, window_seconds=window_seconds)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in self.EXEMPT_PATHS or path.startswith("/assets/"):
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None) or "anonymous"
        result = await self.limiter.check(tenant_id)

        if not result.allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "rate limit exceeded",
                    "limit": result.limit,
                    "current": result.current_count,
                    "retry_after": result.retry_after,
                },
                headers={
                    "Retry-After": str(int(result.retry_after) + 1),
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, result.limit - result.current_count))
        return response
