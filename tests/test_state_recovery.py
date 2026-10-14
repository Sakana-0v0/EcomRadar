"""StateRecovery 单元测试.

断点续跑: 长任务中断后, 从最近 checkpoint 恢复.
"""
import pytest

from app.core.checkpointer import Checkpoint, MemoryCheckpointer
from app.services.governance.state_recovery import (
    StateRecovery,
    RecoveryPlan,
    can_resume_from,
    next_node_after,
)


PIPELINE_ORDER = ["scraper", "extractor", "rag", "writer", "evaluator", "publisher"]


class TestNextNodeAfter:
    def test_returns_next_node(self):
        assert next_node_after(PIPELINE_ORDER, "scraper") == "extractor"

    def test_returns_none_at_end(self):
        assert next_node_after(PIPELINE_ORDER, "publisher") is None

    def test_unknown_node_returns_first(self):
        assert next_node_after(PIPELINE_ORDER, "unknown") == "scraper"


class TestCanResumeFrom:
    def test_can_resume_from_intermediate(self):
        assert can_resume_from(PIPELINE_ORDER, "extractor") is True

    def test_cannot_resume_from_end(self):
        assert can_resume_from(PIPELINE_ORDER, "publisher") is False

    def test_cannot_resume_from_unknown(self):
        assert can_resume_from(PIPELINE_ORDER, "unknown") is False


class TestStateRecovery:
    @pytest.mark.asyncio
    async def test_build_recovery_plan(self):
        store = MemoryCheckpointer()
        await store.save(Checkpoint(
            task_id="t1",
            node_name="writer",
            state={"report": "draft", "retry_count": 1},
        ))
        recovery = StateRecovery(store)
        plan = await recovery.build_plan("t1", pipeline_order=PIPELINE_ORDER)
        assert plan is not None
        assert plan.task_id == "t1"
        assert plan.last_completed_node == "writer"
        assert plan.next_node == "evaluator"
        assert plan.state["report"] == "draft"

    @pytest.mark.asyncio
    async def test_no_checkpoint_returns_none(self):
        store = MemoryCheckpointer()
        recovery = StateRecovery(store)
        plan = await recovery.build_plan("nonexistent", pipeline_order=PIPELINE_ORDER)
        assert plan is None

    @pytest.mark.asyncio
    async def test_resume_at_completed_pipeline(self):
        """所有节点都已完成,无法续跑."""
        store = MemoryCheckpointer()
        for node in PIPELINE_ORDER:
            await store.save(Checkpoint(
                task_id="t1",
                node_name=node,
                state={"v": 1},
            ))
        recovery = StateRecovery(store)
        plan = await recovery.build_plan("t1", pipeline_order=PIPELINE_ORDER)
        assert plan.next_node is None
        assert plan.is_complete is True

    @pytest.mark.asyncio
    async def test_resume_uses_latest_checkpoint(self):
        store = MemoryCheckpointer()
        await store.save(Checkpoint(task_id="t1", node_name="scraper", state={"v": 1}))
        await store.save(Checkpoint(task_id="t1", node_name="extractor", state={"v": 2}))
        await store.save(Checkpoint(task_id="t1", node_name="rag", state={"v": 3}))
        recovery = StateRecovery(store)
        plan = await recovery.build_plan("t1", pipeline_order=PIPELINE_ORDER)
        assert plan.last_completed_node == "rag"
        assert plan.next_node == "writer"
        assert plan.state["v"] == 3

    @pytest.mark.asyncio
    async def test_merge_state_with_override(self):
        store = MemoryCheckpointer()
        await store.save(Checkpoint(
            task_id="t1",
            node_name="rag",
            state={"report": "", "context_docs": ["doc1", "doc2"], "retry_count": 0},
        ))
        recovery = StateRecovery(store)
        plan = await recovery.build_plan("t1", pipeline_order=PIPELINE_ORDER)
        merged = recovery.merge_state(plan.state, {"report": "new", "retry_count": 2})
        assert merged["context_docs"] == ["doc1", "doc2"]
        assert merged["report"] == "new"
        assert merged["retry_count"] == 2


class TestRecoveryPlan:
    def test_plan_to_dict(self):
        plan = RecoveryPlan(
            task_id="t1",
            last_completed_node="scraper",
            next_node="extractor",
            state={"a": 1},
            is_complete=False,
        )
        d = plan.to_dict()
        assert d["task_id"] == "t1"
        assert d["last_completed_node"] == "scraper"
        assert d["next_node"] == "extractor"
        assert d["is_complete"] is False
