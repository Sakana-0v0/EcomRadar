"""Circuit Breaker 三态熔断器.

设计目的:防止下游服务持续不可用时,本系统不断重试浪费资源.
参考: Hystrix / Resilience4j 设计模式.

状态机:
    CLOSED ──[失败率超阈值]──→ OPEN
       ↑                          │
       │                    [recovery_timeout]
       │                          ↓
    [探测成功]                HALF_OPEN
       │                          │
       └──────[探测失败]──────────┘
"""
import asyncio
import functools
import time
from collections import deque
from enum import Enum
from typing import Awaitable, Callable, Optional, TypeVar


T = TypeVar("T")


class CircuitState(str, Enum):
    """熔断器状态枚举."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """熔断器开启时,请求被直接拒绝."""

    def __init__(self, name: str, retry_after: float):
        self.name = name
        self.retry_after = retry_after
        super().__init__(f"circuit '{name}' is OPEN, retry after {retry_after:.1f}s")


class CircuitBreaker:
    """三态熔断器.

    Args:
        name: 熔断器标识
        failure_threshold: 触发熔断的连续失败次数(简化模式)
        window_size: 滑动窗口大小(精确模式)
        failure_rate_threshold: 失败率阈值(0~1), 默认 0.5
        recovery_timeout: OPEN → HALF_OPEN 等待时长(秒)
        expected_exceptions: 视为失败异常类型
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        window_size: int = 10,
        failure_rate_threshold: float = 0.5,
        recovery_timeout: float = 30.0,
        expected_exceptions: Optional[tuple[type[BaseException], ...]] = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.window_size = window_size
        self.failure_rate_threshold = failure_rate_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions or (Exception,)

        self._state = CircuitState.CLOSED
        self._failures: deque[float] = deque(maxlen=window_size)
        self._successes: deque[float] = deque(maxlen=window_size)
        self._opened_at: Optional[float] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    def _now(self) -> float:
        return time.monotonic()

    def _failure_rate(self) -> float:
        total = len(self._failures) + len(self._successes)
        if total == 0:
            return 0.0
        return len(self._failures) / total

    def _should_open(self) -> bool:
        if len(self._failures) >= self.failure_threshold:
            return True
        if (len(self._failures) + len(self._successes)) >= 3:
            if self._failure_rate() >= self.failure_rate_threshold:
                return True
        return False

    def _should_attempt_reset(self) -> bool:
        if self._opened_at is None:
            return False
        return (self._now() - self._opened_at) >= self.recovery_timeout

    def allow_request(self) -> bool:
        """是否允许本次请求通过."""
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                return True
            return False
        return True

    def record_success(self) -> None:
        self._successes.append(self._now())
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._opened_at = None
            self._failures.clear()
        elif self._state == CircuitState.CLOSED:
            if not self._should_open():
                return

    def record_failure(self) -> None:
        self._failures.append(self._now())
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._opened_at = self._now()
        elif self._state == CircuitState.CLOSED:
            if self._should_open():
                self._state = CircuitState.OPEN
                self._opened_at = self._now()

    def force_open(self) -> None:
        """手动强制开启."""
        self._state = CircuitState.OPEN
        self._opened_at = self._now()

    def force_close(self) -> None:
        """手动强制关闭."""
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._failures.clear()
        self._successes.clear()

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "state": self._state.value,
            "failures": len(self._failures),
            "successes": len(self._successes),
            "failure_rate": self._failure_rate(),
            "opened_at": self._opened_at,
        }


def async_circuit_breaker(cb: CircuitBreaker):
    """异步函数熔断装饰器."""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            if not cb.allow_request():
                retry_after = cb.recovery_timeout
                if cb._opened_at is not None:
                    elapsed = cb._now() - cb._opened_at
                    retry_after = max(0.0, cb.recovery_timeout - elapsed)
                raise CircuitOpenError(cb.name, retry_after)
            try:
                result = await func(*args, **kwargs)
            except cb.expected_exceptions:
                cb.record_failure()
                raise
            cb.record_success()
            return result
        return wrapper
    return decorator
