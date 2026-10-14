"""Circuit Breaker 三态熔断器单元测试.

状态机:
- CLOSED: 正常通过,记录失败
- OPEN: 失败过多,直接拒绝
- HALF_OPEN: 探测恢复,放行少量请求

切换条件:
- CLOSED → OPEN: 失败率 ≥ threshold_pct
- OPEN → HALF_OPEN: timeout_seconds 后自动
- HALF_OPEN → CLOSED: 探测成功
- HALF_OPEN → OPEN: 探测仍失败
"""
import asyncio
import time

import pytest

from app.services.governance.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    async_circuit_breaker,
)


class TestCircuitBreaker:
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED

    def test_closed_allows_calls(self):
        cb = CircuitBreaker(name="test")
        assert cb.allow_request() is True

    def test_record_success_in_closed(self):
        cb = CircuitBreaker(name="test")
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold_failures(self):
        """失败率超阈值,熔断器打开."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=3,
            window_size=5,
            failure_rate_threshold=0.5,
        )
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_open_rejects_requests(self):
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            window_size=5,
            failure_rate_threshold=0.5,
        )
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            window_size=5,
            failure_rate_threshold=0.5,
            recovery_timeout=0.1,
        )
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_to_closed_on_success(self):
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            window_size=5,
            failure_rate_threshold=0.5,
            recovery_timeout=0.1,
        )
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.allow_request()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self):
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            window_size=5,
            failure_rate_threshold=0.5,
            recovery_timeout=0.1,
        )
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.allow_request()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_sliding_window_rolls(self):
        """滑动窗口:窗口满后,新失败挤出旧失败."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            window_size=3,
            failure_rate_threshold=0.5,
        )
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert len(cb._failures) == 3
        cb.record_success()
        assert len(cb._failures) == 3
        assert len(cb._successes) == 1

    def test_failure_rate_below_threshold(self):
        cb = CircuitBreaker(
            name="test",
            failure_threshold=10,
            window_size=10,
            failure_rate_threshold=0.5,
        )
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_success()
        cb.record_success()
        cb.record_success()
        cb.record_success()
        cb.record_success()
        cb.record_success()
        cb.record_success()
        assert cb._failure_rate() == pytest.approx(0.2)
        assert cb.state == CircuitState.CLOSED


class TestAsyncCircuitBreakerDecorator:
    @pytest.mark.asyncio
    async def test_passes_through_in_closed(self):
        cb = CircuitBreaker(name="t1", failure_threshold=10)

        @async_circuit_breaker(cb)
        async def fn():
            return "ok"

        result = await fn()
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_failures(self):
        cb = CircuitBreaker(
            name="t2",
            failure_threshold=2,
            window_size=5,
            failure_rate_threshold=0.5,
        )

        @async_circuit_breaker(cb)
        async def fn():
            raise ConnectionError("fail")

        with pytest.raises(ConnectionError):
            await fn()
        with pytest.raises(ConnectionError):
            await fn()

        with pytest.raises(CircuitOpenError):
            await fn()

    @pytest.mark.asyncio
    async def test_recovers_after_timeout(self):
        cb = CircuitBreaker(
            name="t3",
            failure_threshold=2,
            window_size=5,
            failure_rate_threshold=0.5,
            recovery_timeout=0.1,
        )

        call_count = [0]

        @async_circuit_breaker(cb)
        async def fn():
            call_count[0] += 1
            if call_count[0] <= 2:
                raise ConnectionError("fail")
            return "ok"

        with pytest.raises(ConnectionError):
            await fn()
        with pytest.raises(ConnectionError):
            await fn()
        with pytest.raises(CircuitOpenError):
            await fn()

        await asyncio.sleep(0.15)

        result = await fn()
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED


class TestCircuitStateStats:
    def test_stats_tracking(self):
        cb = CircuitBreaker(name="t4", failure_threshold=10, window_size=10)
        cb.record_success()
        cb.record_success()
        cb.record_failure()
        stats = cb.get_stats()
        assert stats["name"] == "t4"
        assert stats["state"] == CircuitState.CLOSED.value
        assert stats["successes"] == 2
        assert stats["failures"] == 1
