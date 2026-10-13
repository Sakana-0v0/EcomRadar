"""Rate Limiter 单元测试 (令牌桶算法)."""
import asyncio
import time

import pytest

from app.services.ecomradar.rate_limiter import TokenBucketRateLimiter, DomainRateLimiter


class TestTokenBucketRateLimiter:
    """TokenBucketRateLimiter 行为测试."""

    @pytest.mark.asyncio
    async def test_acquire_succeeds_when_bucket_has_tokens(self):
        """桶里有 token 时,acquire 立即成功."""
        limiter = TokenBucketRateLimiter(rate=1.0, capacity=5)
        for _ in range(5):
            assert await limiter.acquire() is True

    @pytest.mark.asyncio
    async def test_acquire_blocks_when_bucket_empty(self):
        """桶空时,acquire 阻塞直到有新 token 注入."""
        limiter = TokenBucketRateLimiter(rate=10.0, capacity=1)
        assert await limiter.acquire() is True
        start = time.monotonic()
        assert await limiter.acquire() is True
        elapsed = time.monotonic() - start
        assert elapsed >= 0.08, f"expected ~0.1s wait, got {elapsed:.3f}s"

    @pytest.mark.asyncio
    async def test_capacity_caps_initial_tokens(self):
        """桶容量限制初始 token 数."""
        limiter = TokenBucketRateLimiter(rate=1.0, capacity=3)
        for _ in range(3):
            assert await limiter.acquire() is True
        assert limiter.available_tokens() < 0.5

    @pytest.mark.asyncio
    async def test_concurrent_acquires_respect_rate(self):
        """并发 acquire 严格遵守速率限制."""
        limiter = TokenBucketRateLimiter(rate=5.0, capacity=5)
        start = time.monotonic()
        tasks = [limiter.acquire() for _ in range(10)]
        await asyncio.gather(*tasks)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.9, f"10 reqs at 5/s should take ~1s, got {elapsed:.3f}s"


class TestDomainRateLimiter:
    """DomainRateLimiter 按域名隔离限流."""

    @pytest.mark.asyncio
    async def test_different_domains_have_independent_buckets(self):
        """不同域名使用独立桶,互不影响."""
        limiter = DomainRateLimiter(rate=1.0, capacity=1)
        assert await limiter.acquire("https://a.com/page") is True
        assert await limiter.acquire("https://b.com/page") is True

    @pytest.mark.asyncio
    async def test_same_domain_shares_bucket(self):
        """同一域名共享同一桶."""
        limiter = DomainRateLimiter(rate=1.0, capacity=1)
        assert await limiter.acquire("https://a.com/page1") is True
        assert await limiter.acquire("https://a.com/page2") is True

    @pytest.mark.asyncio
    async def test_invalid_url_returns_false(self):
        """非法 URL 不应抛异常,返回 False."""
        limiter = DomainRateLimiter(rate=1.0, capacity=1)
        assert await limiter.acquire("not-a-valid-url") is False

    @pytest.mark.asyncio
    async def test_extracts_domain_correctly(self):
        """URL → 域名抽取正确."""
        limiter = DomainRateLimiter(rate=1.0, capacity=5)
        assert await limiter.acquire("https://item.jd.com/123.html") is True
        assert await limiter.acquire("http://item.jd.com/456.html") is True
        # 同一域名已用 2 个 token
        assert limiter.bucket_for("https://item.jd.com/789.html").available_tokens() < 4
