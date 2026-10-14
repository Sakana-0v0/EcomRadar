"""Token Manager - Token 生命周期管理.

设计要点:
- 提前 refresh_threshold 秒自动刷新 (默认 5 分钟)
- 缓存当前 token, 避免重复 IO
- 异步锁保护并发刷新 (single-flight)
- 刷新失败时返回旧 token, 标记 expired, 下次强制刷新
- 支持显式 invalidate

应用场景:
- 飞书/Notion API token 刷新
- LLM API 短期 token
- 任何需要 OAuth token 的场景
"""
import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional


class TokenExpiredError(Exception):
    """Token 已彻底过期, 无法继续使用."""


@dataclass
class TokenInfo:
    """Token 信息."""
    access_token: str
    expires_at: float
    refresh_token: Optional[str] = None
    scope: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at

    @property
    def seconds_until_expiry(self) -> float:
        return max(0.0, self.expires_at - time.time())


TokenRefresher = Callable[[], Awaitable[TokenInfo]]


class TokenManager:
    """Token 生命周期管理器.

    Args:
        refresher: 异步函数, 调用时返回新的 TokenInfo
        refresh_threshold: 提前多少秒开始刷新 (默认 300 = 5 分钟)
        clock: 时间函数 (默认 time.time, 测试时可注入)
    """

    def __init__(
        self,
        refresher: TokenRefresher,
        refresh_threshold: float = 300.0,
        clock: Callable[[], float] = time.time,
    ):
        self._refresher = refresher
        self.refresh_threshold = refresh_threshold
        self._clock = clock
        self._cached: Optional[TokenInfo] = None
        self._lock = asyncio.Lock()
        self._last_error: Optional[Exception] = None

    def _should_refresh(self, token: Optional[TokenInfo]) -> bool:
        if token is None:
            return True
        return token.seconds_until_expiry <= self.refresh_threshold

    async def get_token(self) -> TokenInfo:
        """获取当前有效 token (必要时自动刷新)."""
        if self._should_refresh(self._cached):
            await self._refresh()
        assert self._cached is not None
        return self._cached

    async def _refresh(self) -> None:
        """实际刷新 (single-flight, 并发只调一次)."""
        async with self._lock:
            if self._should_refresh(self._cached):
                try:
                    new_token = await self._refresher()
                    self._cached = new_token
                    self._last_error = None
                except Exception as e:
                    self._last_error = e
                    if self._cached is not None and not self._cached.is_expired:
                        return
                    raise TokenExpiredError(
                        f"refresh failed and no cached token: {e}"
                    ) from e

    async def invalidate(self) -> None:
        """显式作废当前 token (强制下次刷新)."""
        async with self._lock:
            self._cached = None

    def get_last_error(self) -> Optional[Exception]:
        return self._last_error
