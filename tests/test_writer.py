import pytest
from app.graph.nodes.writer_node import writer_node
from app.graph.state import GraphState


@pytest.mark.asyncio
async def test_writer_node_increments_retry():
    state: GraphState = {
        "urls": [],
        "scraped_content": {"http://a.com": "内容"},
        "chunks": [],
        "context_docs": [],
        "report": "",
        "quality_score": 0,
        "retry_count": 0,
        "is_degraded": False,
        "error_messages": []
    }
    result = await writer_node(state)
    assert result["retry_count"] == 1
    assert len(result["report"]) > 0