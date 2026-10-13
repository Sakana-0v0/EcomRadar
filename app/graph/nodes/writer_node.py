from app.graph.state import GraphState
from app.services.llm import generate_report
from app.core.logging import get_logger

logger = get_logger(__name__)


async def writer_node(state: GraphState) -> GraphState:
    """Generate research report from scraped content and context."""
    retry_count = state.get("retry_count", 0)
    scraped = state.get("scraped_content", {})
    context = state.get("context_docs", [])

    content = "\n".join(scraped.values())
    context_str = "\n".join(context)

    try:
        logger.info(
            "writer started",
            extra={"node": "writer", "retry_count": retry_count, "content_len": len(content)},
        )
        report = await generate_report(content, context_str, retry_count)
        logger.info(
            "writer completed",
            extra={"node": "writer", "report_len": len(report)},
        )
        return {"report": report, "retry_count": retry_count + 1}
    except Exception as e:
        logger.error(
            "writer failed",
            extra={"node": "writer", "error": str(e)},
        )
        return {
            "report": "",
            "retry_count": retry_count + 1,
            "error_messages": state.get("error_messages", []) + [f"Writer error: {str(e)}"],
            "is_degraded": True,
        }
