from unittest.mock import AsyncMock, patch

import pytest

from app.graph.nodes.writer_node import writer_node
from app.graph.state import GraphState


@pytest.mark.asyncio
async def test_writer_node_increments_retry():
    """writer_node 递增 retry_count 并返回报告."""
    mock_report = """# 竞品周报 - 测试品类

## Executive Summary
本周动态摘要。

## 竞品矩阵对比

| 品牌 | 平台 | 价格 | 销量 | DSR | 关键动作 |
|------|------|------|------|-----|----------|
| A | jd | 100 | 1w+ | 4.8 | - |

## 价格波动分析

| 品牌 | 旧价 | 新价 | 变化 |
|------|------|------|------|
| A | 100 | 100 | → 0.0% |

## 行动建议

**1. 继续观察** — 保持当前策略
"""
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
    with patch(
        "app.graph.nodes.writer_node.generate_competitor_report",
        new=AsyncMock(return_value=mock_report),
    ):
        result = await writer_node(state)

    assert result["retry_count"] == 1
    assert len(result["report"]) > 0