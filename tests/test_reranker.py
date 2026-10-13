"""Lightweight Reranker 单元测试.

多信号融合:
- query_doc_token_overlap: 查询-文档词重叠率
- length_score: 长度惩罚(过长/过短都降权)
- position_score: 位置偏置(早期文档略高分)
- bm25_score_signal: 原始 BM25 分数
"""
import pytest

from app.services.retrieval.reranker import (
    LightweightReranker,
    jaccard_similarity,
    length_score,
    position_score,
    compute_rerank_signals,
)


class TestJaccardSimilarity:
    def test_identical_sets(self):
        assert jaccard_similarity({"a", "b", "c"}, {"a", "b", "c"}) == 1.0

    def test_disjoint_sets(self):
        assert jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        sim = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        assert abs(sim - 0.5) < 1e-6

    def test_empty_set_returns_zero(self):
        assert jaccard_similarity(set(), {"a"}) == 0.0
        assert jaccard_similarity({"a"}, set()) == 0.0


class TestLengthScore:
    def test_optimal_length_gets_max(self):
        score = length_score(text_length=200, optimal=200)
        assert score >= 0.95

    def test_too_short_penalized(self):
        score = length_score(text_length=10, optimal=200)
        assert score < 0.5

    def test_too_long_penalized(self):
        score = length_score(text_length=2000, optimal=200)
        assert score < 0.7

    def test_zero_length(self):
        assert length_score(0, 200) == 0.0


class TestPositionScore:
    def test_first_position_highest(self):
        assert position_score(0, total=10) > position_score(5, total=10)

    def test_last_position_lowest(self):
        assert position_score(9, total=10) < position_score(0, total=10)

    def test_score_in_0_5_to_1(self):
        for i in range(10):
            score = position_score(i, total=10)
            assert 0.5 <= score <= 1.0


class TestComputeRerankSignals:
    def test_returns_dict_with_all_signals(self):
        signals = compute_rerank_signals(
            query="小度音箱",
            doc="小度智能音箱蓝牙",
            bm25_score=5.0,
            position=0,
            total=5,
        )
        assert "token_overlap" in signals
        assert "length_score" in signals
        assert "position_score" in signals
        assert "bm25_signal" in signals
        assert all(0 <= v <= 1 for v in signals.values())


class TestLightweightReranker:
    def test_empty_list_returns_empty(self):
        reranker = LightweightReranker()
        results = reranker.rerank("query", [])
        assert results == []

    def test_rerank_returns_sorted_descending(self):
        reranker = LightweightReranker()
        candidates = [
            {"id": "1", "text": "无关内容xyz", "score": 0.5},
            {"id": "2", "text": "完全匹配关键词", "score": 0.5},
            {"id": "3", "text": "部分匹配 词", "score": 0.5},
        ]
        results = reranker.rerank("完全匹配", candidates, top_k=3)
        assert results[0]["id"] == "2"
        scores = [r["rerank_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_rerank_adds_rerank_score_field(self):
        reranker = LightweightReranker()
        candidates = [
            {"id": "1", "text": "测试内容", "score": 0.5},
        ]
        results = reranker.rerank("测试", candidates)
        assert "rerank_score" in results[0]

    def test_top_k_limits_results(self):
        reranker = LightweightReranker()
        candidates = [{"id": str(i), "text": f"文档 {i}", "score": 0.5} for i in range(20)]
        results = reranker.rerank("文档", candidates, top_k=5)
        assert len(results) == 5

    def test_position_bias_earlier_higher(self):
        """相同内容的文档,位置靠前的 rerank 分数更高."""
        reranker = LightweightReranker(position_weight=0.3)
        candidates = [
            {"id": "early", "text": "完全相同内容", "score": 0.5},
            {"id": "late", "text": "完全相同内容", "score": 0.5},
        ]
        results = reranker.rerank("完全相同", candidates, top_k=2)
        assert results[0]["id"] == "early"

    def test_optimal_length_doc_boosted(self):
        """长度适中的文档应比极短/极长文档得分高."""
        reranker = LightweightReranker(length_weight=0.3)
        candidates = [
            {"id": "short", "text": "x", "score": 0.5},
            {"id": "optimal", "text": "x " * 100, "score": 0.5},
            {"id": "long", "text": "x " * 1000, "score": 0.5},
        ]
        results = reranker.rerank("x", candidates, top_k=3)
        assert results[0]["id"] == "optimal"
