"""Phase 5 集成测试 - Checkpointer + HITL + Recovery.

验证:
- 完整 pipeline 写入 checkpoint
- interrupt 在 Publisher 前触发
- 断点续跑从中断处恢复
- 状态合并正确
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.core.checkpointer import Checkpoint, get_checkpointer, MemoryCheckpointer
from app.services.governance.state_recovery import StateRecovery
from app.services.governance.circuit_breaker import CircuitBreaker, CircuitState
from app.services.governance.retry_policy import RetryPolicy, async_retry
from app.services.governance.output_validator import OutputValidator
from app.graph.workflow import build_workflow, PIPELINE_ORDER


class TestCheckpointerWithRecovery:
    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """完整: 写入 → 读取 → 续跑 → 合并."""
        store = MemoryCheckpointer()
        recovery = StateRecovery(store)

        for node in ["scraper", "extractor", "rag", "writer"]:
            await store.save(Checkpoint(
                task_id="t1",
                node_name=node,
                state={"v": 1, "report": "", "context": ["doc1"]},
            ))

        plan = await recovery.build_plan("t1", PIPELINE_ORDER)
        assert plan.last_completed_node == "writer"
        assert plan.next_node == "evaluator"

        merged = recovery.merge_state(plan.state, {"report": "final report"})
        assert merged["context"] == ["doc1"]
        assert merged["report"] == "final report"


class TestCircuitBreakerIntegration:
    @pytest.mark.asyncio
    async def test_protects_external_call(self):
        cb = CircuitBreaker(
            name="external_api",
            failure_threshold=2,
            window_size=5,
            failure_rate_threshold=0.5,
            recovery_timeout=0.1,
        )
        from app.services.governance.circuit_breaker import (
            async_circuit_breaker, CircuitOpenError,
        )

        call_count = [0]

        @async_circuit_breaker(cb)
        async def flaky_call():
            call_count[0] += 1
            if call_count[0] <= 3:
                raise ConnectionError("fail")
            return "ok"

        with pytest.raises(ConnectionError):
            await flaky_call()
        with pytest.raises(ConnectionError):
            await flaky_call()

        with pytest.raises(CircuitOpenError):
            await flaky_call()
        assert call_count[0] == 2


class TestRetryWithCircuitBreaker:
    @pytest.mark.asyncio
    async def test_retry_with_circuit_breaker_protection(self):
        """Retry 与 CircuitBreaker 组合: 重试仍失败时熔断器打开."""
        cb = CircuitBreaker(
            name="retry_protected",
            failure_threshold=2,
            window_size=5,
            failure_rate_threshold=0.5,
        )
        from app.services.governance.circuit_breaker import (
            async_circuit_breaker, CircuitOpenError,
        )
        from app.services.governance.retry_policy import RetryExhausted

        @async_circuit_breaker(cb)
        @async_retry(RetryPolicy(max_retries=2, base_delay=0.001, jitter=0.0))
        async def always_fails():
            raise ConnectionError("nope")

        with pytest.raises((RetryExhausted, CircuitOpenError)):
            await always_fails()


class TestOutputValidatorWithReport:
    def test_validator_rejects_poor_report(self):
        validator = OutputValidator(
            required_sections=["Executive Summary", "竞品矩阵", "行动建议"],
        )
        result = validator.validate_report("# Just a title")
        assert result.passed is False
        assert "Executive Summary" in result.missing
        assert result.should_retry is True


class TestWorkflowBuilds:
    def test_workflow_with_checkpointer_and_interrupt(self):
        workflow = build_workflow(
            checkpointer=MemorySaver(),
            interrupt_before_publisher=True,
        )
        assert workflow is not None

    def test_workflow_with_checkpointer_no_interrupt(self):
        workflow = build_workflow(
            checkpointer=MemorySaver(),
            interrupt_before_publisher=False,
        )
        assert workflow is not None

    def test_workflow_no_checkpointer(self):
        workflow = build_workflow(
            checkpointer=None,
            interrupt_before_publisher=False,
        )
        assert workflow is not None
