from langgraph.graph import StateGraph, END
from app.graph.state import GraphState
from app.graph.nodes import (
    scraper_node,
    extractor_node,
    rag_node,
    writer_node,
    evaluator_node
)
from app.graph.edges.router import should_retry


def build_workflow() -> StateGraph:
    """Build the LangGraph workflow.

    Flow: Scraper -> Extractor -> RAG -> Writer <-> Evaluator
                              ^                      |
                              --------- retry < 2 ---
    """
    graph = StateGraph(GraphState)

    graph.add_node("scraper", scraper_node)
    graph.add_node("extractor", extractor_node)
    graph.add_node("rag", rag_node)
    graph.add_node("writer", writer_node)
    graph.add_node("evaluator", evaluator_node)

    graph.set_entry_point("scraper")
    graph.add_edge("scraper", "extractor")
    graph.add_edge("extractor", "rag")
    graph.add_edge("rag", "writer")
    graph.add_edge("writer", "evaluator")

    graph.add_conditional_edges(
        "evaluator",
        should_retry,
        {"rewrite": "writer", "end": END}
    )

    return graph.compile()


graph = build_workflow()