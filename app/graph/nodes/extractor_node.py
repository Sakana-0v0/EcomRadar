from app.graph.state import GraphState
from app.services.chunker import chunk_text

def extractor_node(state: GraphState) -> GraphState:
    scraped = state.get("scraped_content", {})
    all_chunks = []
    for content in scraped.values():
        if content:
            chunks = chunk_text(content)
            all_chunks.extend(chunks)
    return {"chunks": all_chunks}
