"""RAG 节点 — 只检索（不再写入主 collection）.

架构:
- knowledge_base: 离线预构建的领域知识（方案 C）
- task_cache: 任务级临时缓存（可选，本次写入以备后续检索）
"""
from app.graph.state import GraphState
from app.services.vector_store import (
    retrieve_from_knowledge_base,
    index_to_task_cache,
    retrieve_from_task_cache,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


async def rag_node(state: GraphState) -> GraphState:
    """从知识库检索相关上下文.

    行为:
    1. 写入 task_cache（供后续可能的中间结果查询）
    2. 从 knowledge_base 检索
    3. 从 task_cache 检索本任务相关内容
    4. 合并结果作为 context_docs
    """
    chunks = state.get("chunks", [])
    urls = state.get("urls", [])
    task_id = state.get("task_id", f"task_{id(state)}")

    if not chunks:
        logger.info("rag skipped: no chunks", extra={"node": "rag"})
        return {"context_docs": [], "is_degraded": True}

    try:
        # 1. 写入 task_cache（任务内可用）
        await index_to_task_cache(task_id, chunks, source=urls[0] if urls else "")

        # 2. 从 KB 检索（核心）
        topic_query = chunks[0][:500]
        kb_results = await retrieve_from_knowledge_base(topic_query, top_k=5)
        kb_docs = [r["text"] for r in kb_results]

        # 3. 从 task_cache 检索本任务（提供重复/相关上下文）
        cache_results = await retrieve_from_task_cache(task_id, topic_query, top_k=3)
        cache_docs = [r["text"] for r in cache_results]

        # 4. 合并（KB 优先，task_cache 补充）
        seen = set()
        merged = []
        for doc in kb_docs + cache_docs:
            key = doc[:50]  # 简单去重
            if key not in seen:
                seen.add(key)
                merged.append(doc)

        logger.info(
            "rag completed",
            extra={
                "node": "rag",
                "kb_hits": len(kb_docs),
                "cache_hits": len(cache_docs),
                "total_context": len(merged),
            },
        )
        return {
            "context_docs": merged,
            "is_degraded": len(merged) == 0,
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
