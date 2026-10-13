"""统一检索管道 (BM25 + Dense + Rerank + Filter + Dedup).

完整流程:
1. Metadata Filter 缩小候选集
2. Hybrid Search (BM25 + Dense) 召回
3. Lightweight Reranker 重排序
4. Semantic Dedup 去重
5. 返回 Top K

可配置各步骤开关,便于 A/B 测试.
"""
import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from app.services.retrieval.bm25_index import BM25Index, tokenize
from app.services.retrieval.hybrid_search import HybridSearcher
from app.services.retrieval.reranker import LightweightReranker
from app.services.retrieval.metadata_filter import MetadataFilter, FilterCriteria
from app.services.retrieval.semantic_dedup import deduplicate_by_jaccard


EmbedFn = Callable[[str], Awaitable[list[float]]]


@dataclass
class RetrievalConfig:
    """检索管道配置."""
    enable_filter: bool = True
    enable_hybrid: bool = True
    enable_rerank: bool = True
    enable_dedup: bool = True
    top_k: int = 5
    candidate_multiplier: int = 3
    dense_weight: float = 0.7
    dedup_threshold: float = 0.7


class RetrievalPipeline:
    """统一检索管道."""

    def __init__(
        self,
        bm25: BM25Index,
        embed_fn: EmbedFn,
        config: Optional[RetrievalConfig] = None,
    ):
        self.bm25 = bm25
        self.embed_fn = embed_fn
        self.config = config or RetrievalConfig()
        self.hybrid = HybridSearcher(
            bm25=bm25,
            embed_fn=embed_fn,
            dense_weight=self.config.dense_weight,
            candidate_multiplier=self.config.candidate_multiplier,
        )
        self.reranker = LightweightReranker()
        self.filter_tool = MetadataFilter()

    def add_documents(self, documents: list[dict]) -> None:
        """添加文档到 BM25 索引."""
        self.bm25.add_documents(documents)

    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_criteria: Optional[FilterCriteria] = None,
    ) -> list[dict]:
        """完整检索流程.

        Args:
            query: 查询字符串
            top_k: 最终返回数量
            filter_criteria: 元数据过滤条件

        Returns:
            最终结果列表
        """
        top_k = top_k or self.config.top_k
        if self.bm25.size() == 0:
            return []

        if self.config.enable_filter and filter_criteria is not None:
            all_docs = self.filter_tool.filter(
                [{"id": str(i), "text": d.text, "source": d.metadata.get("source", ""), "category": d.metadata.get("category", "")}
                 for i, d in enumerate(self.bm25._docs) if d.metadata],
                filter_criteria,
            )

        candidate_k = min(top_k * self.config.candidate_multiplier, self.bm25.size())

        if self.config.enable_hybrid:
            candidates = await self.hybrid.search(query, top_k=candidate_k)
        else:
            candidates = self.bm25.search(query, top_k=candidate_k)

        if not candidates:
            return []

        if self.config.enable_rerank:
            candidates = self.reranker.rerank(query, candidates, top_k=candidate_k)

        if self.config.enable_dedup:
            candidates = deduplicate_by_jaccard(
                candidates,
                threshold=self.config.dedup_threshold,
            )

        return candidates[:top_k]
