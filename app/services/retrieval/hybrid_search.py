"""混合检索: BM25 + Dense 加权融合.

算法:
1. BM25 召回 N 个候选 (N = top_k * 3,扩大召回)
2. Dense 检索 (基于 embed_fn) 计算余弦相似度
3. 分数归一化到 [0, 1]
4. final = dense_weight * dense + (1 - dense_weight) * bm25
5. 按 final 降序,取 top K

设计取舍:
- 权重可配 (默认 dense=0.7, bm25=0.3, 偏向语义)
- dense_weight=0 → 纯 BM25
- dense_weight=1 → 纯 Dense
- 支持外部注入 embed_fn (生产用真实 embedding, 测试用 mock)
"""
import asyncio
import math
from typing import Awaitable, Callable, Optional

from app.services.retrieval.bm25_index import BM25Index


EmbedFn = Callable[[str], Awaitable[list[float]]]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """两个向量的余弦相似度."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """Min-Max 归一化到 [0, 1]."""
    if not scores:
        return {}
    values = list(scores.values())
    min_s, max_s = min(values), max(values)
    if max_s == min_s:
        return {k: 0.0 for k in scores}
    return {k: (v - min_s) / (max_s - min_s) for k, v in scores.items()}


class HybridSearcher:
    """BM25 + Dense 混合检索器."""

    def __init__(
        self,
        bm25: BM25Index,
        embed_fn: EmbedFn,
        dense_weight: float = 0.7,
        candidate_multiplier: int = 3,
    ):
        """初始化.

        Args:
            bm25: BM25 索引
            embed_fn: 异步 embedding 函数
            dense_weight: Dense 权重 (0~1)
            candidate_multiplier: 候选数量倍数 (候选 = top_k * multiplier)
        """
        if not 0 <= dense_weight <= 1:
            raise ValueError("dense_weight must be in [0, 1]")
        self.bm25 = bm25
        self.embed_fn = embed_fn
        self.dense_weight = dense_weight
        self.candidate_multiplier = candidate_multiplier

    async def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """混合检索主入口.

        Args:
            query: 查询字符串
            top_k: 最终返回数量

        Returns:
            [{"id", "text", "score", "bm25_score", "dense_score", ...metadata}, ...]
        """
        if self.bm25.size() == 0:
            return []

        candidate_k = min(top_k * self.candidate_multiplier, self.bm25.size())
        bm25_hits = self.bm25.search(query, top_k=candidate_k)
        if not bm25_hits:
            return []

        query_vector = await self.embed_fn(query)

        bm25_scores: dict[str, float] = {h["id"]: h["score"] for h in bm25_hits}
        dense_scores: dict[str, float] = {}
        for hit in bm25_hits:
            doc_vector = await self.embed_fn(hit["text"])
            dense_scores[hit["id"]] = cosine_similarity(query_vector, doc_vector)

        bm25_norm = normalize_scores(bm25_scores)
        dense_norm = normalize_scores(dense_scores)

        bm25_weight = 1.0 - self.dense_weight
        combined: list[dict] = []
        for hit in bm25_hits:
            doc_id = hit["id"]
            final_score = (
                self.dense_weight * dense_norm.get(doc_id, 0.0)
                + bm25_weight * bm25_norm.get(doc_id, 0.0)
            )
            combined.append({
                **hit,
                "score": final_score,
                "bm25_score": bm25_scores[doc_id],
                "dense_score": dense_scores[doc_id],
            })

        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined[:top_k]
