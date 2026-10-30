"""Middleware 单元测试 (直接测试 dispatch 逻辑, 避免 starlette/httpx 兼容问题)."""
import asyncio
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.middleware import TenantMiddleware, RateLimitMiddleware
from app.services.security.rate_limiter import InMemoryRateLimiter


def _make_request(
    method: str = "GET",
    path: str = "/api/v1/report/generate",
    headers: Optional[dict] = None,
    query_params: Optional[dict] = None,
) -> MagicMock:
    """构造 mock Request 对象."""
    request = MagicMock()
    request.method = method
    request.url.path = path
    request.headers = headers or {}
    request.query_params = query_params or {}
    request.state = MagicMock()
    return request


def _make_response(status_code: int = 200, headers: Optional[dict] = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    return response


def _make_call_next(response: MagicMock) -> AsyncMock:
    async def call_next(request):
        return response
    return call_next


class TestTenantMiddleware:
    @pytest.mark.asyncio
    async def test_tenant_id_injected(self):
        middleware = TenantMiddleware(app=MagicMock())
        request = _make_request(headers={"X-Tenant-ID": "tenant_1"})
        response_mock = _make_response()
        call_next = _make_call_next(response_mock)

        result = await middleware.dispatch(request, call_next)

        assert result.status_code == 200
        assert request.state.tenant_id == "tenant_1"
        assert result.headers["X-Tenant-ID"] == "tenant_1"

    @pytest.mark.asyncio
    async def test_missing_tenant_id_rejected(self):
        from starlette.responses import JSONResponse
        middleware = TenantMiddleware(app=MagicMock(), required=True)
        request = _make_request(headers={})
        call_next = _make_call_next(_make_response())

        result = await middleware.dispatch(request, call_next)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 400
        assert "X-Tenant-ID" in result.body.decode()

    @pytest.mark.asyncio
    async def test_empty_tenant_id_rejected(self):
        from starlette.responses import JSONResponse
        middleware = TenantMiddleware(app=MagicMock(), required=True)
        request = _make_request(headers={"X-Tenant-ID": "   "})
        call_next = _make_call_next(_make_response())

        result = await middleware.dispatch(request, call_next)
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_chars_rejected(self):
        from starlette.responses import JSONResponse
        middleware = TenantMiddleware(app=MagicMock(), required=True)
        request = _make_request(headers={"X-Tenant-ID": "evil@tenant"})
        call_next = _make_call_next(_make_response())

        result = await middleware.dispatch(request, call_next)
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_health_path_exempt(self):
        middleware = TenantMiddleware(app=MagicMock(), required=True)
        request = _make_request(path="/api/v1/health", headers={})
        call_next = _make_call_next(_make_response())

        result = await middleware.dispatch(request, call_next)
        assert result.status_code == 200
        assert request.state.tenant_id == "anonymous"

    @pytest.mark.asyncio
    async def test_user_id_optional(self):
        middleware = TenantMiddleware(app=MagicMock())
        request = _make_request(headers={"X-Tenant-ID": "t1", "X-User-ID": "u1"})
        call_next = _make_call_next(_make_response())

        await middleware.dispatch(request, call_next)
        assert request.state.user_id == "u1"

    @pytest.mark.asyncio
    async def test_tenant_from_query_param(self):
        """EventSource 场景: tenant_id 通过 query param 传递."""
        middleware = TenantMiddleware(app=MagicMock(), required=True)
        request = _make_request(headers={}, query_params={"tenant_id": "tenant_q"})
        call_next = _make_call_next(_make_response())

        result = await middleware.dispatch(request, call_next)
        assert result.status_code == 200
        assert request.state.tenant_id == "tenant_q"


class TestRateLimitMiddleware:
    @pytest.mark.asyncio
    async def test_under_limit_allowed(self):
        limiter = InMemoryRateLimiter(limit=3, window_seconds=60.0)
        middleware = RateLimitMiddleware(app=MagicMock(), limiter=limiter)
        request = _make_request()
        request.state.tenant_id = "t1"
        response_mock = _make_response(headers={})
        call_next = _make_call_next(response_mock)

        for _ in range(3):
            result = await middleware.dispatch(request, call_next)
            assert result.status_code == 200
            assert "X-RateLimit-Limit" in result.headers

    @pytest.mark.asyncio
    async def test_over_limit_returns_429(self):
        from starlette.responses import JSONResponse
        limiter = InMemoryRateLimiter(limit=2, window_seconds=60.0)
        middleware = RateLimitMiddleware(app=MagicMock(), limiter=limiter)
        request = _make_request()
        request.state.tenant_id = "t1"
        call_next = _make_call_next(_make_response())

        for _ in range(2):
            result = await middleware.dispatch(request, call_next)
            assert result.status_code == 200

        result = await middleware.dispatch(request, call_next)
        assert isinstance(result, JSONResponse)
        assert result.status_code == 429
        assert "Retry-After" in result.headers
        assert "X-RateLimit-Limit" in result.headers

    @pytest.mark.asyncio
    async def test_different_tenants_independent(self):
        limiter = InMemoryRateLimiter(limit=1, window_seconds=60.0)
        middleware = RateLimitMiddleware(app=MagicMock(), limiter=limiter)
        call_next = _make_call_next(_make_response())

        req1 = _make_request()
        req1.state.tenant_id = "t1"
        result_a1 = await middleware.dispatch(req1, call_next)
        result_a2 = await middleware.dispatch(req1, call_next)
        assert result_a1.status_code == 200
        assert result_a2.status_code == 429

        req2 = _make_request()
        req2.state.tenant_id = "t2"
        result_b1 = await middleware.dispatch(req2, call_next)
        assert result_b1.status_code == 200

    @pytest.mark.asyncio
    async def test_health_path_exempt(self):
        limiter = InMemoryRateLimiter(limit=1, window_seconds=60.0)
        middleware = RateLimitMiddleware(app=MagicMock(), limiter=limiter)
        request = _make_request(path="/api/v1/health")
        request.state.tenant_id = "t1"
        call_next = _make_call_next(_make_response())

        for _ in range(5):
            result = await middleware.dispatch(request, call_next)
            assert result.status_code == 200
