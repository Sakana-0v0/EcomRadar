"""Workflow 编译 - Checkpointer + interrupt 集成.

完整 6 节点: scraper → extractor → rag → writer → evaluator ↻ publisher
- Evaluator → Writer: 质量不达标重试 (≤2 次)
- Evaluator → Publisher: 质量达标进入发布
- Publisher 前 interrupt_before: Human-in-the-Loop
- 全节点写入 Checkpointer

注: LangGraph 的 checkpointer 需使用 langgraph.checkpoint 接口;
我们自定义的 CheckpointStore 用于 StateRecovery (Phase 5 配套 API),
二者并存,各司其职.
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import GraphState
from app.graph.nodes import (
    scraper_node,
    extractor_node,
    rag_node,
    writer_node,
    evaluator_node,
    publisher_node,
)
from app.graph.edges.router import should_retry, should_publish


PIPELINE_ORDER = ["scraper", "extractor", "rag", "writer", "evaluator", "publisher"]


def build_workflow(
    checkpointer=None,
    interrupt_before_publisher: bool = True,
) -> StateGraph:
    """构建 LangGraph 工作流.

    Args:
        checkpointer: LangGraph 兼容的 checkpointer (None = 不持久化)
        interrupt_before_publisher: Publisher 节点前是否触发 HITL
    """
    graph = StateGraph(GraphState)

    graph.add_node("scraper", scraper_node)
    graph.add_node("extractor", extractor_node)
    graph.add_node("rag", rag_node)
    graph.add_node("writer", writer_node)
    graph.add_node("evaluator", evaluator_node)
    graph.add_node("publisher", publisher_node)

    graph.set_entry_point("scraper")
    graph.add_edge("scraper", "extractor")
    graph.add_edge("extractor", "rag")
    graph.add_edge("rag", "writer")
    graph.add_edge("writer", "evaluator")

    graph.add_conditional_edges(
        "evaluator",
        should_retry,
        {"rewrite": "writer", "publish": "publisher", "end": END},
    )
    graph.add_edge("publisher", END)

    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
    if interrupt_before_publisher:
        compile_kwargs["interrupt_before"] = ["publisher"]

    return graph.compile(**compile_kwargs)


def build_default_workflow():
    """构建默认工作流 (LangGraph MemorySaver + 启用 HITL)."""
    return build_workflow(
        checkpointer=MemorySaver(),
        interrupt_before_publisher=True,
    )


graph = build_default_workflow()
