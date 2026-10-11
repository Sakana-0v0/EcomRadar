"""LangGraph 状态图流转单测"""
import pytest
from app.graph.workflow import graph
from app.graph.state import GraphState


def test_workflow_compiles():
    assert graph is not None


@pytest.mark.asyncio
async def test_workflow_run():
    state: GraphState = {
        "urls": ["https://example.com"],
        "scraped_content": {},
        "chunks": [],
        "context_docs": [],
        "report": "",
        "quality_score": 0,
        "retry_count": 0,
        "is_degraded": False,
        "error_messages": []
    }
    result = await graph.ainvoke(state)
    assert "report" in result