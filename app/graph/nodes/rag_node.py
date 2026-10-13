"""RAG Node 升级 - 集成混合检索管道.

行为:
1. 从 scraped_content 抽取 query
2. 用 RetrievalPipeline 检索 KB
3. 应用 metadata filter (platform / category)
4. 应用 semantic dedup
5. 返回 context_docs
"""
from app.graph.state import GraphState
from app.core.logging import get_logger

logger = get_logger(__name__)


_PIPELINE = None


def _get_pipeline():
    """懒加载检索管道 (单例)."""
    global _PIPELINE
    if _PIPELINE is None:
        from app.services.retrieval.bm25_index import BM25Index
        from app.services.retrieval.retrieval_pipeline import RetrievalPipeline
        from app.services.embedding import embed_text

        bm25 = BM25Index()

        try:
            from data.kb_sources.ecom_industry_notes_loader import load_industry_notes
            docs = load_industry_notes()
        except Exception:
            docs = []
        if docs:
            bm25.add_documents(docs)

        _PIPELINE = RetrievalPipeline(
            bm25=bm25,
            embed_fn=embed_text,
        )
    return _PIPELINE


async def rag_node(state: GraphState) -> GraphState:
    """RAG Node v2 - 集成 BM25 + Dense + Rerank + Filter + Dedup.

    输入: chunks (从 scraped_content 抽取的文本块)
    输出: context_docs (Top-K 检索结果)
    """
    chunks = state.get("chunks", [])
    urls = state.get("urls", [])
    task_id = state.get("task_id", f"task_{id(state)}")

    if not chunks:
        logger.info("rag skipped: no chunks", extra={"node": "rag"})
        return {"context_docs": [], "is_degraded": True}

    query = " ".join(chunks[:3])[:500] if chunks else "电商竞品"

    try:
        pipeline = _get_pipeline()
        results = await pipeline.search(query, top_k=5)

        context_docs = [r["text"] for r in results if r.get("text")]

        logger.info(
            "rag completed",
            extra={
                "node": "rag",
                "hits": len(results),
                "context_chars": sum(len(d) for d in context_docs),
            },
        )
        return {
            "context_docs": context_docs,
            "is_degraded": len(context_docs) == 0,
        }
    except Exception as e:
        logger.error(
            "rag failed",
            extra={"node": "rag", "error": str(e)},
        )
        return {
            "context_docs": [],
            "is_degraded": True,
            "error_messages": state.get("error_messages", []) + [f"RAG error: {str(e)}"],
        }
