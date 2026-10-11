from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

_client = None

def get_client() -> QdrantClient:
    """Get or create Qdrant client singleton."""
    global _client
    if _client is None:
        _client = QdrantClient(host="localhost", port=6333)
    return _client

def retrieve_context(query: str, top_k: int = 5) -> list[str]:
    """Retrieve top-k context documents from Qdrant vector store.

    Args:
        query: Search query string
        top_k: Number of results to retrieve

    Returns:
        List of context document texts
    """
    client = get_client()
    try:
        results = client.search(
            collection_name="reports",
            query_vector=query,
            limit=top_k
        )
        return [result.payload.get("text", "") for result in results]
    except Exception:
        return []
