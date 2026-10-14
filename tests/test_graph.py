"""LangGraph 状态图编译单测."""
import pytest
from langgraph.checkpoint.memory import MemorySaver
from unittest.mock import AsyncMock, patch

from app.graph.workflow import build_workflow, PIPELINE_ORDER


def test_workflow_compiles():
    """工作流能正常编译."""
    workflow = build_workflow(checkpointer=None, interrupt_before_publisher=False)
    assert workflow is not None


def test_workflow_compiles_with_checkpointer():
    """带 Checkpointer 编译."""
    workflow = build_workflow(
        checkpointer=MemorySaver(),
        interrupt_before_publisher=True,
    )
    assert workflow is not None


def test_workflow_compiles_without_interrupt():
    """不带 HITL 的工作流."""
    workflow = build_workflow(
        checkpointer=MemorySaver(),
        interrupt_before_publisher=False,
    )
    assert workflow is not None


def test_pipeline_order_includes_publisher():
    """PIPELINE_ORDER 包含 6 个节点."""
    assert len(PIPELINE_ORDER) == 6
    assert "scraper" in PIPELINE_ORDER
    assert "publisher" in PIPELINE_ORDER
