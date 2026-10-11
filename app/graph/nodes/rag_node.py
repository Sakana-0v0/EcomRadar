from app.graph.state import GraphState
from app.services.vector_store import retrieve_context

def rag_node(state: GraphState) -> GraphState:
    chunks = state.get("chunks", [])
    if not chunks:
        return {"context_docs": []}
    topic = chunks[0][:100]
    context = retrieve_context(topic, top_k=5)
    return {"context_docs": context}
