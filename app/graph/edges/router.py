from app.graph.state import GraphState


def should_retry(state: GraphState) -> str:
    """Determine if the workflow should retry or end.

    Returns:
        "rewrite" if quality < 75 and retries < 2
        "end" otherwise
    """
    quality = state.get("quality_score", 0)
    retry = state.get("retry_count", 0)
    if quality >= 75 or retry >= 2:
        return "end"
    return "rewrite"