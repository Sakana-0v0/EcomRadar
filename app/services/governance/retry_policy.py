"""Retry Policy - 指数退避 + jitter.

设计要点:
- 指数退避: 避免雪崩, 减少并发冲突
- Jitter (随机扰动): 防止惊群效应 (thundering herd)
- 最大延迟上限: 防止单次等待过长
- 可重试异常白名单: 区分瞬时故障 vs 业务错误
- 装饰器 async_retry: 一行接入, 业务代码零侵入
"""
import asyncio
import functools
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, TypeVar


T = TypeVar("T")


class RetryExhausted(Exception):
    """超过最大重试次数."""

    def __init__(self, last_exception: BaseException, attempts: int):
        self.last_exception = last_exception
        self.attempts = attempts
        super().__init__(f"retry exhausted after {attempts} attempts: {last_exception}")


def compute_backoff(
    attempt: int,
    base: float = 1.0,
    max_delay: float = 60.0,
    jitter: float = 0.1,
) -> float:
    """计算第 N 次重试前的等待时长(秒).

    Args:
        attempt: 已失败次数(0 表示还没失败)
        base: 基础延迟(秒)
        max_delay: 最大延迟上限
        jitter: 随机扰动比例(0~1,默认 10%)

    Returns:
        等待秒数
    """
    if attempt <= 0:
        return 0.0
    exponential = base * (2 ** (attempt - 1))
    if jitter > 0:
        delta = exponential * jitter
        exponential = exponential + random.uniform(-delta, delta)
    return min(max_delay, max(0.0, exponential))


@dataclass
class RetryPolicy:
    """重试策略配置."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: float = 0.1
    retryable_exceptions: Optional[frozenset[type[BaseException]]] = None

    def __post_init__(self):
        if self.retryable_exceptions is None:
            self.retryable_exceptions = frozenset({
                ConnectionError, TimeoutError, asyncio.TimeoutError,
            })

    def should_retry(self, attempt: int) -> bool:
        """基于已失败次数,判断是否还能再尝试.

        attempt 含义: 已失败次数 (0 = 第一次,还未失败)
        max_retries=3 含义: 最多 3 次尝试
        - attempt=0 (刚开始): True
        - attempt=2 (失败 2 次): True
        - attempt=3 (失败 3 次): False → RetryExhausted
        """
        return attempt < self.max_retries

    def should_retry_with_exception(
        self,
        attempt: int,
        exception: BaseException,
    ) -> bool:
        if not self.should_retry(attempt):
            return False
        if self.retryable_exceptions is None:
            return True
        return type(exception) in self.retryable_exceptions

    def is_exhausted(self, attempt: int) -> bool:
        """已用尽所有尝试(超过则抛 RetryExhausted)."""
        return attempt >= self.max_retries

    def delay_for_attempt(self, attempt: int) -> float:
        return compute_backoff(
            attempt=attempt,
            base=self.base_delay,
            max_delay=self.max_delay,
            jitter=self.jitter,
        )


def async_retry(
    policy: RetryPolicy,
    on_retry: Optional[Callable[[int, BaseException], Awaitable[None]]] = None,
):
    """异步函数重试装饰器.

    Args:
        policy: 重试策略
        on_retry: 每次重试前的回调 (attempt, exception)

    Example:
        policy = RetryPolicy(max_retries=3, base_delay=1.0)

        @async_retry(policy)
        async def call_external_api():
            ...
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exc: BaseException | None = None
            for attempt in range(policy.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except BaseException as e:
                    last_exc = e
                    if policy.is_exhausted(attempt):
                        raise RetryExhausted(e, attempt) from e
                    if not policy.should_retry_with_exception(attempt, e):
                        raise
                    delay = policy.delay_for_attempt(attempt + 1)
                    if on_retry is not None:
                        try:
                            await on_retry(attempt + 1, e)
                        except Exception:
                            pass
                    if delay > 0:
                        await asyncio.sleep(delay)
            raise RetryExhausted(last_exc, policy.max_retries + 1)
        return wrapper
    return decorator
