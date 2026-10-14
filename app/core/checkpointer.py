"""Checkpointer - 状态持久化抽象.

两种后端:
- MemoryCheckpointer: 内存,开发/测试用
- PostgresCheckpointer: PostgreSQL,生产用 (使用 langgraph-checkpoint-postgres)

设计原则:
- 统一接口 CheckpointStore
- 异步 API
- 保留完整历史(支持断点续跑与审计)
"""
import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Checkpoint:
    """单个状态快照."""
    task_id: str
    node_name: str
    state: dict
    next_nodes: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


class CheckpointStore(ABC):
    """Checkpoint 存储抽象接口."""

    @abstractmethod
    async def save(self, checkpoint: Checkpoint) -> None:
        """保存一个 checkpoint."""
        ...

    @abstractmethod
    async def load(self, task_id: str) -> Optional[Checkpoint]:
        """加载 task 的最新 checkpoint."""
        ...

    @abstractmethod
    async def get_history(self, task_id: str) -> list[Checkpoint]:
        """获取 task 的所有历史 checkpoint (按时间升序)."""
        ...

    @abstractmethod
    async def get_latest(self, task_id: str) -> Optional[Checkpoint]:
        """获取 task 的最新 checkpoint."""
        ...

    @abstractmethod
    async def clear(self, task_id: str) -> None:
        """清空 task 的所有 checkpoint."""
        ...


class MemoryCheckpointer(CheckpointStore):
    """内存版 Checkpoint 存储."""

    def __init__(self):
        self._store: dict[str, list[Checkpoint]] = {}
        self._lock = asyncio.Lock()

    async def save(self, checkpoint: Checkpoint) -> None:
        async with self._lock:
            if checkpoint.task_id not in self._store:
                self._store[checkpoint.task_id] = []
            self._store[checkpoint.task_id].append(checkpoint)

    async def load(self, task_id: str) -> Optional[Checkpoint]:
        async with self._lock:
            history = self._store.get(task_id, [])
            return history[-1] if history else None

    async def get_history(self, task_id: str) -> list[Checkpoint]:
        async with self._lock:
            return list(self._store.get(task_id, []))

    async def get_latest(self, task_id: str) -> Optional[Checkpoint]:
        return await self.load(task_id)

    async def clear(self, task_id: str) -> None:
        async with self._lock:
            self._store.pop(task_id, None)

    def size(self) -> int:
        return sum(len(v) for v in self._store.values())


class PostgresCheckpointer(CheckpointStore):
    """PostgreSQL 版 Checkpoint 存储 (生产级)."""

    def __init__(self, connection_string: str, table_name: str = "ecomradar_checkpoints"):
        self.connection_string = connection_string
        self.table_name = table_name
        self._pool = None

    async def _ensure_pool(self):
        if self._pool is None:
            try:
                import asyncpg
                self._pool = await asyncpg.create_pool(self.connection_string)
                async with self._pool.acquire() as conn:
                    await conn.execute(f"""
                        CREATE TABLE IF NOT EXISTS {self.table_name} (
                            id SERIAL PRIMARY KEY,
                            task_id TEXT NOT NULL,
                            node_name TEXT NOT NULL,
                            state JSONB NOT NULL,
                            next_nodes JSONB,
                            metadata JSONB,
                            created_at TIMESTAMPTZ DEFAULT NOW()
                        );
                        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_task_id
                            ON {self.table_name} (task_id, created_at DESC);
                    """)
            except ImportError:
                raise RuntimeError(
                    "asyncpg not installed. Run: pip install asyncpg"
                )

    async def save(self, checkpoint: Checkpoint) -> None:
        await self._ensure_pool()
        import json
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {self.table_name}
                    (task_id, node_name, state, next_nodes, metadata)
                    VALUES ($1, $2, $3, $4, $5)""",
                checkpoint.task_id,
                checkpoint.node_name,
                json.dumps(checkpoint.state, ensure_ascii=False, default=str),
                json.dumps(checkpoint.next_nodes),
                json.dumps(checkpoint.metadata, ensure_ascii=False, default=str),
            )

    async def load(self, task_id: str) -> Optional[Checkpoint]:
        await self._ensure_pool()
        import json
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT task_id, node_name, state, next_nodes, metadata, created_at
                    FROM {self.table_name}
                    WHERE task_id = $1
                    ORDER BY created_at DESC LIMIT 1""",
                task_id,
            )
            if row is None:
                return None
            return Checkpoint(
                task_id=row["task_id"],
                node_name=row["node_name"],
                state=json.loads(row["state"]) if isinstance(row["state"], str) else row["state"],
                next_nodes=json.loads(row["next_nodes"]) if isinstance(row["next_nodes"], str) else (row["next_nodes"] or []),
                metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}),
                created_at=row["created_at"].timestamp(),
            )

    async def get_history(self, task_id: str) -> list[Checkpoint]:
        await self._ensure_pool()
        import json
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT task_id, node_name, state, next_nodes, metadata, created_at
                    FROM {self.table_name}
                    WHERE task_id = $1
                    ORDER BY created_at ASC""",
                task_id,
            )
        checkpoints: list[Checkpoint] = []
        for row in rows:
            checkpoints.append(Checkpoint(
                task_id=row["task_id"],
                node_name=row["node_name"],
                state=json.loads(row["state"]) if isinstance(row["state"], str) else row["state"],
                next_nodes=json.loads(row["next_nodes"]) if isinstance(row["next_nodes"], str) else (row["next_nodes"] or []),
                metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}),
                created_at=row["created_at"].timestamp(),
            ))
        return checkpoints

    async def get_latest(self, task_id: str) -> Optional[Checkpoint]:
        return await self.load(task_id)

    async def clear(self, task_id: str) -> None:
        await self._ensure_pool()
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"DELETE FROM {self.table_name} WHERE task_id = $1",
                task_id,
            )


def get_checkpointer(
    backend: str = "memory",
    connection_string: Optional[str] = None,
) -> CheckpointStore:
    """工厂函数: 按配置返回 Checkpointer."""
    if backend == "memory":
        return MemoryCheckpointer()
    if backend == "postgres":
        if not connection_string:
            raise ValueError("PostgresCheckpointer requires connection_string")
        return PostgresCheckpointer(connection_string=connection_string)
    raise ValueError(f"unknown checkpointer backend: {backend}")
