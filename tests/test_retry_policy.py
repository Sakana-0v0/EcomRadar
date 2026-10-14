"""RetryPolicy 指数退避 + jitter 单元测试."""
import asyncio
import time

import pytest

from app.services.governance.retry_policy import (
    RetryPolicy,
    RetryExhausted,
    async_retry,
    compute_backoff,
)


class TestComputeBackoff:
    def test_first_attempt_no_delay(self):
        assert compute_backoff(0, base=1.0) == 0

    def test_exponential_growth(self):
        b1 = compute_backoff(1, base=1.0, jitter=0.0)
        b2 = compute_backoff(2, base=1.0, jitter=0.0)
        b3 = compute_backoff(3, base=1.0, jitter=0.0)
        assert b1 == 1.0
        assert b2 == 2.0
        assert b3 == 4.0

    def test_max_delay_cap(self):
        b = compute_backoff(20, base=1.0, max_delay=30.0, jitter=0.0)
        assert b <= 30.0

    def test_jitter_within_range(self):
        for _ in range(50):
            b = compute_backoff(3, base=1.0, jitter=0.5)
            assert 2.0 <= b <= 6.0

    def test_jitter_zero_is_deterministic(self):
        for _ in range(10):
            assert compute_backoff(2, base=1.0, jitter=0.0) == 2.0


class TestRetryPolicy:
    def test_should_retry_under_max(self):
        policy = RetryPolicy(max_retries=3)
        assert policy.should_retry(attempt=0) is True
        assert policy.should_retry(attempt=2) is True
        assert policy.should_retry(attempt=3) is False

    def test_should_retry_respects_retryable_exceptions(self):
        policy = RetryPolicy(
            max_retries=3,
            retryable_exceptions={TimeoutError, ConnectionError},
        )
        assert policy.should_retry_with_exception(0, TimeoutError("x")) is True
        assert policy.should_retry_with_exception(0, ValueError("x")) is False

    def test_delay_calculation(self):
        policy = RetryPolicy(max_retries=5, base_delay=1.0, jitter=0.0)
        assert policy.delay_for_attempt(0) == 0.0
        assert policy.delay_for_attempt(1) == 1.0
        assert policy.delay_for_attempt(2) == 2.0
        assert policy.delay_for_attempt(3) == 4.0


class TestAsyncRetryDecorator:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        calls = []

        @async_retry(RetryPolicy(max_retries=3))
        async def fn():
            calls.append(1)
            return "ok"

        result = await fn()
        assert result == "ok"
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self):
        calls = []

        @async_retry(RetryPolicy(max_retries=3, base_delay=0.001, jitter=0.0))
        async def fn():
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("fail")
            return "ok"

        result = await fn()
        assert result == "ok"
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        calls = []

        @async_retry(RetryPolicy(max_retries=2, base_delay=0.001, jitter=0.0))
        async def fn():
            calls.append(1)
            raise TimeoutError("always fail")

        with pytest.raises(RetryExhausted):
            await fn()
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception_raises_immediately(self):
        calls = []

        @async_retry(RetryPolicy(max_retries=5, retryable_exceptions={ValueError}))
        async def fn():
            calls.append(1)
            raise TypeError("not retryable")

        with pytest.raises(TypeError):
            await fn()
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_total_elapsed_time_with_backoff(self):
        policy = RetryPolicy(max_retries=3, base_delay=0.05, jitter=0.0)
        start = time.monotonic()

        @async_retry(policy)
        async def fn():
            raise ConnectionError("x")

        with pytest.raises(RetryExhausted):
            await fn()
        elapsed = time.monotonic() - start
        # 0 + 0.05 + 0.10 = 0.15s min
        assert elapsed >= 0.1
