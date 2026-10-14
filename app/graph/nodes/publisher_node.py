"""Publisher Node - 6 节点 + HITL 触发点.

行为:
1. 接收合格报告
2. 等待 human approval (通过 LangGraph interrupt_before)
3. approval 后, 推送报告到 MCP 通道 (Notion / 飞书)

HITL 触发: workflow 编译时配置 interrupt_before=["publisher"]
"""
import asyncio
from typing import Any

from app.graph.state import GraphState
from app.core.logging import get_logger
from app.core.checkpointer import Checkpoint, get_checkpointer

logger = get_logger(__name__)


async def publisher_node(state: GraphState) -> GraphState:
    """Publisher Node - 推送报告到外部平台.

    输入: 合格报告 + task_id
    输出: published_channels (list[str])

    注: 此节点由 LangGraph interrupt 机制保护.
    实际执行需先调用 POST /resume 审批通过.
    """
    report = state.get("report", "")
    task_id = state.get("task_id", f"task_{id(state)}")

    if not report:
        return {
            "published_channels": [],
            "is_degraded": True,
            "error_messages": state.get("error_messages", []) + ["Publisher: empty report"],
        }

    published_channels: list[str] = []

    try:
        from app.core.mcp_config import get_publishers
        publishers = get_publishers()

        for publisher in publishers:
            try:
                await publisher.publish(
                    title=f"EcomRadar Report - {state.get('report_category', '未指定')}",
                    content=report,
                    metadata={"task_id": task_id, "category": state.get("report_category")},
                )
                published_channels.append(publisher.channel_name)
            except Exception as e:
                logger.warning(
                    f"publisher {publisher.channel_name} failed",
                    extra={"node": "publisher", "error": str(e)},
                )

        checkpoint_store = get_checkpointer(backend="memory")
        await checkpoint_store.save(Checkpoint(
            task_id=task_id,
            node_name="publisher",
            state={**state, "published_channels": published_channels},
        ))

        logger.info(
            "publisher completed",
            extra={"node": "publisher", "channels": published_channels},
        )
        return {"published_channels": published_channels}

    except Exception as e:
        logger.error("publisher failed", extra={"node": "publisher", "error": str(e)})
        return {
            "published_channels": [],
            "is_degraded": True,
            "error_messages": state.get("error_messages", []) + [f"Publisher: {str(e)}"],
        }
