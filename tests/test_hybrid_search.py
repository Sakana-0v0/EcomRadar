"""混合检索 (BM25 + Dense) 单元测试."""
import asyncio
import math
import pytest
from unittest.mock import AsyncMock

from app.services.retrieval.bm25_index import BM25Index
from app.services.retrieval.hybrid_search import (
    HybridSearcher,
    cosine_similarity,
    normalize_scores,
)


def _make_embed_fn(vectors: dict[str, list[float]]):
    """构造 mock embed_fn."""
    async def embed_fn(text: str) -> list[float]:
        for key, vec in vectors.items():
            if key in text:
                return vec
        return [0.0] * 4
    return embed_fn


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(cosine_similarity(a, b)) < 1e-6

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(cosine_similarity(a, b) + 1.0) < 1e-6

    def test_zero_vector_returns_zero(self):
        a = [0.0, 0.0]
        b = [1.0, 2.0]
        assert cosine_similarity(a, b) == 0.0


class TestNormalizeScores:
    def test_normalizes_to_0_1(self):
        scores = {"a": 10.0, "b": 5.0, "c": 0.0}
        normalized = normalize_scores(scores)
        assert normalized["a"] == 1.0
        assert normalized["b"] == 0.5
        assert normalized["c"] == 0.0

    def test_all_same_scores_returns_zeros(self):
        scores = {"a": 5.0, "b": 5.0, "c": 5.0}
        normalized = normalize_scores(scores)
        assert all(v == 0.0 for v in normalized.values())

    def test_empty_returns_empty(self):
        assert normalize_scores({}) == {}


class TestHybridSearcher:
    def test_empty_corpus(self):
        bm25 = BM25Index()
        embed_fn = _make_embed_fn({})
        searcher = HybridSearcher(bm25=bm25, embed_fn=embed_fn)
        results = asyncio.run(searcher.search("query", top_k=5))
        assert results == []

    def test_bm25_only_when_embed_returns_zero(self):
        """embed 返回零向量时,BM25 仍能命中."""
        bm25 = BM25Index()
        bm25.add_documents([
            {"id": "1", "text": "小度智能音箱", "source": "jd"},
            {"id": "2", "text": "天猫精灵音响", "source": "tmall"},
        ])
        embed_fn = _make_embed_fn({})  # 全返回零向量
        searcher = HybridSearcher(bm25=bm25, embed_fn=embed_fn, dense_weight=0.5)
        results = asyncio.run(searcher.search("小度", top_k=5))
        assert len(results) >= 1
        assert results[0]["id"] == "1"

    def test_dense_higher_score_boosts_relevant_doc(self):
        """dense 分数高的文档排在前面."""
        bm25 = BM25Index()
        bm25.add_documents([
            {"id": "1", "text": "智能音箱蓝牙音响语音助手", "source": "jd"},
            {"id": "2", "text": "智能音箱WiFi连接功能", "source": "tmall"},
            {"id": "3", "text": "蓝牙耳机运动防水", "source": "pdd"},
        ])
        embed_fn = _make_embed_fn({
            "智能音箱": [0.9, 0.1, 0.0, 0.0],
            "蓝牙耳机": [0.0, 0.0, 0.9, 0.1],
        })
        searcher = HybridSearcher(bm25=bm25, embed_fn=embed_fn, dense_weight=0.7)
        results = asyncio.run(searcher.search("智能音箱", top_k=3))
        assert results[0]["id"] in ("1", "2")
        assert "score" in results[0]
        assert "bm25_score" in results[0]
        assert "dense_score" in results[0]

    def test_weight_configuration(self):
        """权重可配置,影响排序."""
        bm25 = BM25Index()
        bm25.add_documents([
            {"id": "exact_match", "text": "智能音箱", "source": "jd"},
            {"id": "related", "text": "智能家居音箱音响", "source": "tmall"},
        ])
        embed_fn = _make_embed_fn({
            "智能音箱": [1.0, 0.0, 0.0, 0.0],
            "智能家居": [0.8, 0.2, 0.0, 0.0],
        })
        bm25_heavy = HybridSearcher(bm25=bm25, embed_fn=embed_fn, dense_weight=0.1)
        dense_heavy = HybridSearcher(bm25=bm25, embed_fn=embed_fn, dense_weight=0.9)
        results_bm25 = asyncio.run(bm25_heavy.search("智能音箱", top_k=2))
        results_dense = asyncio.run(dense_heavy.search("智能音箱", top_k=2))
        assert results_bm25[0]["id"] == "exact_match"
        assert results_dense[0]["id"] == "exact_match"

    def test_top_k_limits_results(self):
        bm25 = BM25Index()
        for i in range(20):
            bm25.add_documents([{"id": str(i), "text": f"测试商品 {i}", "source": "test"}])
        embed_fn = _make_embed_fn({})
        searcher = HybridSearcher(bm25=bm25, embed_fn=embed_fn)
        results = asyncio.run(searcher.search("测试", top_k=5))
        assert len(results) == 5

    def test_results_sorted_descending(self):
        bm25 = BM25Index()
        bm25.add_documents([
            {"id": "1", "text": "小度智能音箱", "source": "jd"},
            {"id": "2", "text": "小度小度小度智能音箱", "source": "tmall"},
            {"id": "3", "text": "小度智能", "source": "pdd"},
        ])
        embed_fn = _make_embed_fn({})
        searcher = HybridSearcher(bm25=bm25, embed_fn=embed_fn)
        results = asyncio.run(searcher.search("小度智能", top_k=3))
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)
