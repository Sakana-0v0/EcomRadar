"""TokenManager 单元测试.

Token 生命周期管理:
- 提前 refresh_threshold 秒自动刷新 (默认 300s = 5min)
- 缓存当前 token, 避免重复 IO
- 异步锁保护并发刷新
- 刷新失败时, 标记 expired, 下次调用强制刷新
"""
import asyncio
import time
from typing import Optional

import pytest

from app.services.security.token_manager import (
    TokenManager,
    TokenInfo,
    TokenExpiredError,
)


class FakeTokenRefresher:
    """模拟 token 刷新器 (测试用).

    fail_on_calls: 在指定 call 编号上失败 (1-indexed)
    例如 fail_on_calls=[2] 表示第 2 次调用失败
    """

    def __init__(self, ttl_seconds: int = 3600, fail_on_calls: Optional[list[int]] = None):
        self.ttl = ttl_seconds
        self.call_count = 0
        self.fail_on_calls = fail_on_calls or []
        self._counter = 0

    async def __call__(self) -> TokenInfo:
        self.call_count += 1
        if self.call_count in self.fail_on_calls:
            raise ConnectionError(f"refresh failed on call #{self.call_count}")
        self._counter += 1
        return TokenInfo(
            access_token=f"token-{self._counter}",
            expires_at=time.time() + self.ttl,
            refresh_token=f"refresh-{self._counter}",
        )


class TestTokenManager:
    @pytest.mark.asyncio
    async def test_first_call_triggers_refresh(self):
        refresher = FakeTokenRefresher()
        mgr = TokenManager(refresher=refresher, refresh_threshold=300.0)
        token = await mgr.get_token()
        assert token.access_token == "token-1"
        assert refresher.call_count == 1

    @pytest.mark.asyncio
    async def test_subsequent_calls_use_cache(self):
        refresher = FakeTokenRefresher()
        mgr = TokenManager(refresher=refresher, refresh_threshold=300.0)
        await mgr.get_token()
        await mgr.get_token()
        await mgr.get_token()
        assert refresher.call_count == 1

    @pytest.mark.asyncio
    async def test_refresh_before_expiry(self):
        """TTL 即将耗尽前, 自动刷新."""
        refresher = FakeTokenRefresher(ttl_seconds=10)
        mgr = TokenManager(refresher=refresher, refresh_threshold=300.0)
        first = await mgr.get_token()
        # 模拟时间流逝, 让 token 接近过期
        first.expires_at = time.time() + 100  # 100s 后过期
        mgr._cached = first
        second = await mgr.get_token()
        assert second.access_token == "token-2"
        assert refresher.call_count == 2

    @pytest.mark.asyncio
    async def test_concurrent_first_call_single_refresh(self):
        """并发首次调用只刷新一次."""
        refresher = FakeTokenRefresher()
        mgr = TokenManager(refresher=refresher, refresh_threshold=300.0)
        results = await asyncio.gather(*[mgr.get_token() for _ in range(10)])
        assert all(r.access_token == "token-1" for r in results)
        assert refresher.call_count == 1

    @pytest.mark.asyncio
    async def test_refresh_failure_cached_token_kept(self):
        """刷新失败时, 仍返回旧 token (避免完全中断)."""
        # 第一次成功, 第二次失败, 第三次成功
        refresher = FakeTokenRefresher(fail_on_calls=[2])
        mgr = TokenManager(refresher=refresher, refresh_threshold=300.0)
        # 第一次: 成功获取 token-1
        first = await mgr.get_token()
        assert first.access_token == "token-1"
        # 强制下一次刷新 (token 即将过期)
        first.expires_at = time.time() + 100
        mgr._cached = first
        # 第二次: 刷新失败, 但 token 仍有效, 返回旧 token
        second = await mgr.get_token()
        assert second.access_token == "token-1"

    @pytest.mark.asyncio
    async def test_invalidate_forces_refresh(self):
        refresher = FakeTokenRefresher()
        mgr = TokenManager(refresher=refresher, refresh_threshold=300.0)
        await mgr.get_token()
        await mgr.invalidate()
        new_token = await mgr.get_token()
        assert new_token.access_token == "token-2"
        assert refresher.call_count == 2

    def test_should_refresh_logic(self):
        mgr = TokenManager(refresher=FakeTokenRefresher(), refresh_threshold=300.0)
        assert mgr._should_refresh(None) is True
        valid = TokenInfo(access_token="x", expires_at=time.time() + 1000)
        assert mgr._should_refresh(valid) is False
        near_expiry = TokenInfo(access_token="x", expires_at=time.time() + 100)
        assert mgr._should_refresh(near_expiry) is True


class TestTokenInfo:
    def test_is_expired(self):
        from app.services.security.token_manager import TokenInfo
        token = TokenInfo(access_token="x", expires_at=time.time() - 10)
        assert token.is_expired is True

    def test_not_expired(self):
        token = TokenInfo(access_token="x", expires_at=time.time() + 100)
        assert token.is_expired is False

    def test_seconds_until_expiry(self):
        token = TokenInfo(access_token="x", expires_at=time.time() + 50)
        assert 45 <= token.seconds_until_expiry <= 55
