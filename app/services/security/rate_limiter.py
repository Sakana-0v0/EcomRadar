"""SlidingWindowRateLimiter - 多租户分布式限流.

算法: 滑动窗口
- 维护一个时间窗口(如 60s)
- 窗口内累计请求数 ≤ 阈值
- 旧请求自动滚出窗口

两种后端:
- InMemoryRateLimiter: 单进程,开发/测试
- RedisRateLimiter: 跨进程,生产级 (需要 redis 库)

设计原则:
- 抽象基类 + 工厂方法,业务代码无感切换
- 异步 API, 与 asyncio 生态兼容
- 限流 key 按 tenant_id 或 user_id 隔离
"""
import asyncio
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class RateLimitResult:
    """限流结果."""
    allowed: bool
    current_count: int
    limit: int
    retry_after: float = 0.0
    key: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class RateLimiterBackend(ABC):
    """限流后端抽象基类."""

    @abstractmethod
    async def check(self, key: str) -> RateLimitResult:
        """检查 key 是否允许通过, 原子操作."""
        ...

    @abstractmethod
    async def reset(self, key: str) -> None:
        """重置 key 计数."""
        ...


class InMemoryRateLimiter(RateLimiterBackend):
    """内存版限流器.

    适用场景: 单进程开发/测试,或低并发场景.
    生产环境请使用 RedisRateLimiter.
    """

    def __init__(self, limit: int, window_seconds: float):
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._windows: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> RateLimitResult:
        async with self._lock:
            now = time.monotonic()
            window = self._windows.setdefault(key, deque())
            cutoff = now - self.window_seconds
            while window and window[0] < cutoff:
                window.popleft()

            if len(window) >= self.limit:
                retry_after = window[0] + self.window_seconds - now
                return RateLimitResult(
                    allowed=False,
                    current_count=len(window),
                    limit=self.limit,
                    retry_after=max(0.0, retry_after),
                    key=key,
                )

            window.append(now)
            return RateLimitResult(
                allowed=True,
                current_count=len(window),
                limit=self.limit,
                retry_after=0.0,
                key=key,
            )

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._windows.pop(key, None)


class RedisRateLimiter(RateLimiterBackend):
    """Redis 版限流器 (生产级).

    使用 ZSET 维护滑动窗口:
    - member: 唯一请求 ID
    - score: 时间戳
    - ZREMRANGEBYSCORE 清除过期
    - ZCARD 获取当前窗口大小
    - 全部用 Lua 脚本保证原子性

    依赖: pip install redis
    """

    LUA_SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    local req_id = ARGV[4]

    redis.call('ZREMRANGEBYSCORE', key, 0, now - window * 1000)
    local count = redis.call('ZCARD', key)
    if count >= limit then
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local retry_after = (tonumber(oldest[2]) + window * 1000 - now) / 1000
        return {0, count, retry_after}
    end
    redis.call('ZADD', key, now, req_id)
    redis.call('EXPIRE', key, window)
    return {1, count + 1, 0}
    """

    def __init__(self, limit: int, window_seconds: float, redis_url: str = "redis://localhost:6379/0"):
        if limit <= 0:
            raise ValueError("limit must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self.redis_url = redis_url
        self._client = None
        self._script = None

    async def _get_client(self):
        if self._client is None:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(self.redis_url, decode_responses=True)
            self._script = self._client.register_script(self.LUA_SCRIPT)
        return self._client

    async def check(self, key: str) -> RateLimitResult:
        client = await self._get_client()
        now_ms = int(time.time() * 1000)
        req_id = f"{now_ms}:{key}:{id(self)}"
        try:
            allowed, count, retry_after = await self._script(
                keys=[f"rl:{key}"],
                args=[now_ms, self.window_seconds, self.limit, req_id],
            )
        except Exception:
            return RateLimitResult(
                allowed=True, current_count=0, limit=self.limit, key=key,
            )
        return RateLimitResult(
            allowed=bool(int(allowed)),
            current_count=int(count),
            limit=self.limit,
            retry_after=float(retry_after),
            key=key,
        )

    async def reset(self, key: str) -> None:
        client = await self._get_client()
        await client.delete(f"rl:{key}")


class SlidingWindowRateLimiter:
    """限流器工厂与配置入口."""

    @staticmethod
    def create(
        backend: str = "memory",
        limit: int = 10,
        window_seconds: float = 60.0,
        redis_url: Optional[str] = None,
    ) -> RateLimiterBackend:
        """根据配置创建后端.

        Args:
            backend: "memory" 或 "redis"
            limit: 时间窗口内最大请求数
            window_seconds: 窗口大小(秒)
            redis_url: Redis 连接 URL(仅 redis 后端)
        """
        if backend == "memory":
            return InMemoryRateLimiter(limit=limit, window_seconds=window_seconds)
        if backend == "redis":
            if not redis_url:
                redis_url = "redis://localhost:6379/0"
            return RedisRateLimiter(limit=limit, window_seconds=window_seconds, redis_url=redis_url)
        raise ValueError(f"unknown rate limiter backend: {backend}")
