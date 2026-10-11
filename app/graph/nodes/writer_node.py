from app.graph.state import GraphState


async def writer_node(state: GraphState) -> GraphState:
    """Generate research report from scraped content and context.

    For demo purposes, this is a mock implementation that creates
    a simple structured report. In production, this would call an LLM.
    """
    retry_count = state.get("retry_count", 0)
    scraped = state.get("scraped_content", {})
    context = state.get("context_docs", [])

    content_summary = "".join(scraped.values())[:500]
    context_summary = "".join(context)[:200]

    report = f"""# 研究报告

## 核心要点
基于 {len(scraped)} 个信息源生成

## 内容摘要
{content_summary}

## 上下文参考
{context_summary}

---
*本报告为 Demo 版本（重试次数: {retry_count}）*
"""
    return {
        "report": report,
        "retry_count": retry_count + 1
    }