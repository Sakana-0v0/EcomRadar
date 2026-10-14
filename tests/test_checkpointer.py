"""Checkpointer 单元测试.

支持两种后端:
- MemoryCheckpointer: 内存 (开发/测试)
- PostgresCheckpointer: PostgreSQL (生产)
"""
import asyncio
import time

import pytest

from app.core.checkpointer import (
    CheckpointStore,
    MemoryCheckpointer,
    Checkpoint,
    get_checkpointer,
)


SAMPLE_STATE = {
    "urls": ["https://example.com"],
    "scraped_content": {"url": "content"},
    "report": "",
    "retry_count": 0,
    "quality_score": 0,
}


class TestCheckpoint:
    def test_creation(self):
        cp = Checkpoint(
            task_id="t1",
            node_name="scraper",
            state=SAMPLE_STATE,
            next_nodes=["extractor"],
        )
        assert cp.task_id == "t1"
        assert cp.node_name == "scraper"
        assert cp.created_at > 0


class TestMemoryCheckpointer:
    @pytest.mark.asyncio
    async def test_save_and_load(self):
        cp = MemoryCheckpointer()
        checkpoint = Checkpoint(
            task_id="t1",
            node_name="scraper",
            state=SAMPLE_STATE,
        )
        await cp.save(checkpoint)
        loaded = await cp.load("t1")
        assert loaded is not None
        assert loaded.task_id == "t1"
        assert loaded.state == SAMPLE_STATE

    @pytest.mark.asyncio
    async def test_load_nonexistent_returns_none(self):
        cp = MemoryCheckpointer()
        loaded = await cp.load("nonexistent")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_save_overwrites(self):
        cp = MemoryCheckpointer()
        await cp.save(Checkpoint(task_id="t1", node_name="a", state={"v": 1}))
        await cp.save(Checkpoint(task_id="t1", node_name="b", state={"v": 2}))
        loaded = await cp.load("t1")
        assert loaded.node_name == "b"
        assert loaded.state == {"v": 2}

    @pytest.mark.asyncio
    async def test_get_history(self):
        cp = MemoryCheckpointer()
        await cp.save(Checkpoint(task_id="t1", node_name="scraper", state={}))
        await cp.save(Checkpoint(task_id="t1", node_name="extractor", state={}))
        await cp.save(Checkpoint(task_id="t1", node_name="rag", state={}))
        history = await cp.get_history("t1")
        assert len(history) == 3
        assert [c.node_name for c in history] == ["scraper", "extractor", "rag"]

    @pytest.mark.asyncio
    async def test_get_latest(self):
        cp = MemoryCheckpointer()
        await cp.save(Checkpoint(task_id="t1", node_name="a", state={}))
        await cp.save(Checkpoint(task_id="t1", node_name="b", state={}))
        latest = await cp.get_latest("t1")
        assert latest.node_name == "b"

    @pytest.mark.asyncio
    async def test_clear(self):
        cp = MemoryCheckpointer()
        await cp.save(Checkpoint(task_id="t1", node_name="a", state={}))
        await cp.clear("t1")
        loaded = await cp.load("t1")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_concurrent_saves_isolated(self):
        cp = MemoryCheckpointer()

        async def save_task(task_id: str, value: int):
            await cp.save(Checkpoint(task_id=task_id, node_name="x", state={"v": value}))

        await asyncio.gather(*[save_task(f"t{i}", i) for i in range(10)])
        for i in range(10):
            loaded = await cp.load(f"t{i}")
            assert loaded.state["v"] == i


class TestCheckpointerFactory:
    def test_get_checkpointer_returns_memory_by_default(self):
        cp = get_checkpointer(backend="memory")
        assert isinstance(cp, MemoryCheckpointer)

    def test_get_checkpointer_postgres_requires_url(self):
        from app.core.checkpointer import PostgresCheckpointer
        cp = get_checkpointer(backend="postgres", connection_string="postgresql://localhost/test")
        assert isinstance(cp, PostgresCheckpointer)
