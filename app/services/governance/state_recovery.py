"""State Recovery - 断点续跑.

能力:
- 从最近 checkpoint 恢复
- 推算 next_node (基于 pipeline 顺序)
- 支持状态合并 (override + preserve)
"""
from dataclasses import dataclass, field, asdict
from typing import Optional

from app.core.checkpointer import Checkpoint, CheckpointStore


@dataclass
class RecoveryPlan:
    """断点续跑计划."""
    task_id: str
    last_completed_node: Optional[str]
    next_node: Optional[str]
    state: dict = field(default_factory=dict)
    is_complete: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def next_node_after(pipeline_order: list[str], current: str) -> Optional[str]:
    """根据 pipeline 顺序, 获取当前节点的下一节点."""
    if current not in pipeline_order:
        return pipeline_order[0] if pipeline_order else None
    idx = pipeline_order.index(current)
    if idx + 1 < len(pipeline_order):
        return pipeline_order[idx + 1]
    return None


def can_resume_from(pipeline_order: list[str], node_name: str) -> bool:
    """是否可以从该节点续跑 (非末尾节点)."""
    if node_name not in pipeline_order:
        return False
    return pipeline_order.index(node_name) < len(pipeline_order) - 1


class StateRecovery:
    """断点续跑服务."""

    def __init__(self, store: CheckpointStore):
        self.store = store

    async def build_plan(
        self,
        task_id: str,
        pipeline_order: list[str],
    ) -> Optional[RecoveryPlan]:
        """构建续跑计划.

        Args:
            task_id: 任务 ID
            pipeline_order: 节点顺序列表

        Returns:
            RecoveryPlan,无 checkpoint 时返回 None
        """
        history = await self.store.get_history(task_id)
        if not history:
            return None

        latest = history[-1]
        next_node = next_node_after(pipeline_order, latest.node_name)
        is_complete = next_node is None

        return RecoveryPlan(
            task_id=task_id,
            last_completed_node=latest.node_name,
            next_node=next_node,
            state=dict(latest.state),
            is_complete=is_complete,
            metadata={
                "checkpoint_count": len(history),
                "saved_at": latest.created_at,
            },
        )

    def merge_state(
        self,
        base: dict,
        override: dict,
    ) -> dict:
        """合并状态: override 覆盖 base 字段, 其他保留.

        Args:
            base: 基础状态 (来自 checkpoint)
            override: 覆盖字段 (来自 API 请求等)

        Returns:
            合并后状态
        """
        merged = dict(base)
        merged.update(override)
        return merged
