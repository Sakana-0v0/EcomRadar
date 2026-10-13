from app.graph.state import GraphState
from app.services.chunker import chunk_text
from app.core.logging import get_logger

logger = get_logger(__name__)


def extractor_node(state: GraphState) -> GraphState:
    scraped = state.get("scraped_content", {})
    all_chunks = []
    try:
        for content in scraped.values():
            if content:
                chunks = chunk_text(content)
                all_chunks.extend(chunks)
        logger.info(
            "extractor completed",
            extra={"node": "extractor", "chunk_count": len(all_chunks)},
        )
        return {"chunks": all_chunks}
    except Exception as e:
        logger.error(
            "extractor failed",
            extra={"node": "extractor", "error": str(e)},
        )
        return {
            "chunks": [],
            "error_messages": state.get("error_messages", []) + [f"Extractor error: {str(e)}"],
        }
