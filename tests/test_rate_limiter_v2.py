"""SlidingWindowRateLimiter 单元测试.

支持两种后端:
- InMemoryRateLimiter: 内存,开发/测试
- RedisRateLimiter: Redis,生产分布式

算法: 滑动窗口(Sliding Window)
- 维护一个时间窗口(如 60s)
- 窗口内累计请求数 ≤ 阈值
- 旧请求自动滚出窗口
"""
import asyncio
import time

import pytest

from app.services.security.rate_limiter import (
    SlidingWindowRateLimiter,
    InMemoryRateLimiter,
    RateLimitResult,
)


class TestRateLimitResult:
    def test_allowed(self):
        r = RateLimitResult(allowed=True, current_count=5, limit=10, retry_after=0.0)
        assert r.allowed is True

    def test_rejected(self):
        r = RateLimitResult(allowed=False, current_count=11, limit=10, retry_after=5.0)
        assert r.allowed is False
        assert r.retry_after == 5.0

    def test_to_dict(self):
        r = RateLimitResult(allowed=True, current_count=3, limit=10, retry_after=0.0)
        d = r.to_dict()
        assert d["allowed"] is True
        assert d["limit"] == 10


class TestInMemoryRateLimiter:
    @pytest.mark.asyncio
    async def test_under_limit_allowed(self):
        limiter = InMemoryRateLimiter(limit=5, window_seconds=60.0)
        for _ in range(5):
            result = await limiter.check("tenant_1")
            assert result.allowed is True

    @pytest.mark.asyncio
    async def test_over_limit_rejected(self):
        limiter = InMemoryRateLimiter(limit=3, window_seconds=60.0)
        for _ in range(3):
            result = await limiter.check("tenant_1")
            assert result.allowed is True
        result = await limiter.check("tenant_1")
        assert result.allowed is False
        assert result.retry_after > 0

    @pytest.mark.asyncio
    async def test_different_keys_independent(self):
        """不同 key (tenant) 独立计数."""
        limiter = InMemoryRateLimiter(limit=2, window_seconds=60.0)
        await limiter.check("tenant_1")
        await limiter.check("tenant_1")
        result_a = await limiter.check("tenant_1")
        result_b = await limiter.check("tenant_2")
        assert result_a.allowed is False
        assert result_b.allowed is True

    @pytest.mark.asyncio
    async def test_window_slides(self):
        """窗口滑动:旧请求滚出后,配额恢复."""
        limiter = InMemoryRateLimiter(limit=2, window_seconds=0.2)
        await limiter.check("tenant_1")
        await limiter.check("tenant_1")
        result = await limiter.check("tenant_1")
        assert result.allowed is False
        await asyncio.sleep(0.25)
        result_after = await limiter.check("tenant_1")
        assert result_after.allowed is True

    @pytest.mark.asyncio
    async def test_concurrent_safe(self):
        """并发安全."""
        limiter = InMemoryRateLimiter(limit=10, window_seconds=60.0)

        async def hit():
            return await limiter.check("tenant_1")

        results = await asyncio.gather(*[hit() for _ in range(20)])
        allowed = sum(1 for r in results if r.allowed)
        rejected = sum(1 for r in results if not r.allowed)
        assert allowed == 10
        assert rejected == 10

    def test_factory_returns_inmemory_when_redis_missing(self):
        limiter = SlidingWindowRateLimiter.create(
            backend="memory", limit=10, window_seconds=60.0
        )
        assert isinstance(limiter, InMemoryRateLimiter)
