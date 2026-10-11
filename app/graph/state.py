from typing import TypedDict


class GraphState(TypedDict):
    urls: list[str]
    scraped_content: dict[str, str]
    chunks: list[str]
    context_docs: list[str]
    report: str
    quality_score: int
    retry_count: int
    is_degraded: bool
    error_messages: list[str]
