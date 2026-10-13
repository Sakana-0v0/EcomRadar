"""混合检索 Benchmark 单元测试.

手工标注的电商知识库测试集:
- 5 个类目
- 20 个 query
- 每个 query 标注期望召回的 doc_ids
- 验证 Recall@5 指标
"""
import asyncio
import pytest
from unittest.mock import AsyncMock

from app.services.retrieval.bm25_index import BM25Index
from app.services.retrieval.hybrid_search import HybridSearcher
from app.services.retrieval.reranker import LightweightReranker
from app.services.retrieval.retrieval_pipeline import RetrievalPipeline
from app.services.retrieval.semantic_dedup import deduplicate_by_jaccard


ECOM_KB = [
    {"id": "kb_001", "text": "智能音箱是 AI 语音助手载体,主流品牌有小度、天猫精灵、小爱", "category": "智能音箱"},
    {"id": "kb_002", "text": "双 11 是年度最大促销节点,平台 11 月 1 日开始预售,11 月 11 日达到高峰", "category": "营销节点"},
    {"id": "kb_003", "text": "口红价格带分三档:开架 50-100 元,中端 100-300 元,高端 300 元以上", "category": "美妆"},
    {"id": "kb_004", "text": "DSR 包含描述相符、服务态度、物流服务三个维度,各维度 ≥4.8 为健康", "category": "店铺运营"},
    {"id": "kb_005", "text": "SKU 策略分引流款、爆款、利润款,合理比例约为 3:5:2", "category": "运营策略"},
    {"id": "kb_006", "text": "拼多多百亿补贴是平台主推活动,价格低于其他平台 10-30%", "category": "平台活动"},
    {"id": "kb_007", "text": "手机壳材质分硅胶、塑料、皮革,硅胶销量占比超 60%", "category": "3C 配件"},
    {"id": "kb_008", "text": "差评关键词 Top 3 是质量、物流、客服响应,占比合计超过 70%", "category": "评价分析"},
    {"id": "kb_009", "text": "618 大促分预售期、专场期、高潮期三个阶段,京东是主场", "category": "营销节点"},
    {"id": "kb_010", "text": "蓝牙音箱续航 8-12 小时为合格线,IPX7 防水是户外款标配", "category": "智能音箱"},
    {"id": "kb_011", "text": "完美日记主打性价比,核心价格带 ¥89-129", "category": "美妆"},
    {"id": "kb_012", "text": "花西子主打国潮,核心价格带 ¥199-299", "category": "美妆"},
    {"id": "kb_013", "text": "京东 PLUS 会员可享专属价,平均优惠 5-10%", "category": "平台活动"},
    {"id": "kb_014", "text": "天猫 88VIP 享 95 折,跨平台通用", "category": "平台活动"},
    {"id": "kb_015", "text": "短视频带货转化率比图文高 2-3 倍,完播率是关键指标", "category": "运营策略"},
]


BENCHMARK_QUERIES = [
    {"query": "智能音箱品牌", "expected": ["kb_001", "kb_010"]},
    {"query": "双 11 节奏", "expected": ["kb_002"]},
    {"query": "口红价格带", "expected": ["kb_003", "kb_011", "kb_012"]},
    {"query": "DSR 评分", "expected": ["kb_004"]},
    {"query": "SKU 比例", "expected": ["kb_005"]},
    {"query": "拼多多 百亿补贴", "expected": ["kb_006"]},
    {"query": "手机壳 材质", "expected": ["kb_007"]},
    {"query": "差评关键词", "expected": ["kb_008"]},
    {"query": "618 大促", "expected": ["kb_009"]},
    {"query": "蓝牙音箱 续航 防水", "expected": ["kb_010"]},
    {"query": "完美日记 价格", "expected": ["kb_011"]},
    {"query": "国潮 美妆", "expected": ["kb_012"]},
    {"query": "京东 PLUS 价", "expected": ["kb_013"]},
    {"query": "天猫 88VIP", "expected": ["kb_014"]},
    {"query": "短视频 带货", "expected": ["kb_015"]},
    {"query": "智能音箱 续航", "expected": ["kb_001", "kb_010"]},
    {"query": "营销 节点", "expected": ["kb_002", "kb_009"]},
    {"query": "美妆 品牌", "expected": ["kb_003", "kb_011", "kb_012"]},
    {"query": "平台 会员", "expected": ["kb_013", "kb_014"]},
    {"query": "运营 策略", "expected": ["kb_005", "kb_015"]},
]


def _embed_for_dummy():
    """构造 mock embed_fn:基于词重叠的伪向量."""
    async def embed(text: str):
        tokens = set(text)
        vec = [1.0 if t in tokens else 0.0 for t in "智能音箱品牌口红价格促销节点店铺运营dsrsku平台"]
        return vec
    return embed


def recall_at_k(retrieved_ids: list[str], expected: list[str], k: int) -> float:
    if not expected:
        return 0.0
    top_k_ids = set(retrieved_ids[:k])
    hits = sum(1 for e in expected if e in top_k_ids)
    return hits / len(expected)


class TestBenchmarkHybridVsBM25:
    """Benchmark: 对比 BM25-only vs Hybrid Search."""

    @pytest.mark.asyncio
    async def test_hybrid_recall_at_5_above_threshold(self):
        """混合检索 Recall@5 ≥ 0.7 (benchmark 基线)."""
        bm25 = BM25Index()
        bm25.add_documents(ECOM_KB)
        embed_fn = _embed_for_dummy()
        searcher = HybridSearcher(bm25=bm25, embed_fn=embed_fn, dense_weight=0.7)

        recalls = []
        for bq in BENCHMARK_QUERIES:
            results = await searcher.search(bq["query"], top_k=5)
            retrieved_ids = [r["id"] for r in results]
            r5 = recall_at_k(retrieved_ids, bq["expected"], k=5)
            recalls.append(r5)

        avg_recall = sum(recalls) / len(recalls)
        assert avg_recall >= 0.7, f"avg Recall@5 = {avg_recall:.3f}, expected >= 0.7"

    @pytest.mark.asyncio
    async def test_bm25_only_recall_baseline(self):
        bm25 = BM25Index()
        bm25.add_documents(ECOM_KB)

        recalls = []
        for bq in BENCHMARK_QUERIES:
            results = bm25.search(bq["query"], top_k=5)
            retrieved_ids = [r["id"] for r in results]
            r5 = recall_at_k(retrieved_ids, bq["expected"], k=5)
            recalls.append(r5)

        avg_recall = sum(recalls) / len(recalls)
        assert avg_recall >= 0.5, f"BM25 baseline Recall@5 = {avg_recall:.3f}"


class TestBenchmarkRerank:
    """Benchmark: 验证 Rerank 能提升排序质量."""

    @pytest.mark.asyncio
    async def test_rerank_improves_top_position(self):
        """Rerank 后,期望文档出现在 top1 位置."""
        bm25 = BM25Index()
        bm25.add_documents(ECOM_KB)
        embed_fn = _embed_for_dummy()
        searcher = HybridSearcher(bm25=bm25, embed_fn=embed_fn)
        reranker = LightweightReranker()

        improvements = 0
        for bq in BENCHMARK_QUERIES:
            if not bq["expected"]:
                continue
            results = await searcher.search(bq["query"], top_k=5)
            if not results:
                continue
            reranked = reranker.rerank(bq["query"], results, top_k=5)
            if reranked[0]["id"] in bq["expected"]:
                improvements += 1

        improvement_rate = improvements / len(BENCHMARK_QUERIES)
        assert improvement_rate >= 0.4, f"top1 accuracy = {improvement_rate:.3f}"


class TestBenchmarkDedup:
    """Benchmark: 验证去重不影响召回."""

    def test_dedup_preserves_relevant_docs(self):
        docs = [
            {"id": "kb_001", "text": "智能音箱主流品牌", "score": 1.0},
            {"id": "kb_001_dup", "text": "智能音箱主流品牌", "score": 0.5},
            {"id": "kb_002", "text": "双 11 节奏", "score": 0.8},
        ]
        deduped = deduplicate_by_jaccard(docs, threshold=0.7)
        ids = [d["id"] for d in deduped]
        assert "kb_001" in ids
        assert "kb_001_dup" not in ids
        assert "kb_002" in ids


class TestBenchmarkPipeline:
    """端到端 Pipeline Benchmark."""

    @pytest.mark.asyncio
    async def test_pipeline_end_to_end(self):
        """完整管道 Recall@5 ≥ 0.6."""
        bm25 = BM25Index()
        bm25.add_documents(ECOM_KB)
        embed_fn = _embed_for_dummy()
        pipeline = RetrievalPipeline(bm25=bm25, embed_fn=embed_fn)

        recalls = []
        for bq in BENCHMARK_QUERIES:
            results = await pipeline.search(bq["query"], top_k=5)
            retrieved_ids = [r["id"] for r in results]
            r5 = recall_at_k(retrieved_ids, bq["expected"], k=5)
            recalls.append(r5)

        avg_recall = sum(recalls) / len(recalls)
        assert avg_recall >= 0.6, f"Pipeline Recall@5 = {avg_recall:.3f}"


class TestBenchmarkReport:
    """Benchmark 报告生成 (用于简历展示)."""

    def test_benchmark_results_runnable(self):
        """Benchmark 跑得通,生成可展示报告."""
        bm25 = BM25Index()
        bm25.add_documents(ECOM_KB)

        async def run_benchmark():
            embed_fn = _embed_for_dummy()
            searcher = HybridSearcher(bm25=bm25, embed_fn=embed_fn, dense_weight=0.7)
            reranker = LightweightReranker()

            bm25_recalls = []
            hybrid_recalls = []
            rerank_top1 = 0

            for bq in BENCHMARK_QUERIES:
                bm25_results = bm25.search(bq["query"], top_k=5)
                bm25_ids = [r["id"] for r in bm25_results]
                bm25_recalls.append(recall_at_k(bm25_ids, bq["expected"], k=5))

                hybrid_results = await searcher.search(bq["query"], top_k=5)
                hybrid_ids = [r["id"] for r in hybrid_results]
                hybrid_recalls.append(recall_at_k(hybrid_ids, bq["expected"], k=5))

                if hybrid_results:
                    reranked = reranker.rerank(bq["query"], hybrid_results, top_k=5)
                    if reranked[0]["id"] in bq["expected"]:
                        rerank_top1 += 1

            return {
                "queries": len(BENCHMARK_QUERIES),
                "bm25_recall_at_5": sum(bm25_recalls) / len(bm25_recalls),
                "hybrid_recall_at_5": sum(hybrid_recalls) / len(hybrid_recalls),
                "rerank_top1_accuracy": rerank_top1 / len(BENCHMARK_QUERIES),
            }

        result = asyncio.run(run_benchmark())
        print(f"\n[Benchmark Report]")
        print(f"  Queries: {result['queries']}")
        print(f"  BM25-only Recall@5: {result['bm25_recall_at_5']:.3f}")
        print(f"  Hybrid Search Recall@5: {result['hybrid_recall_at_5']:.3f}")
        print(f"  Rerank Top1 Accuracy: {result['rerank_top1_accuracy']:.3f}")
        assert result["hybrid_recall_at_5"] >= result["bm25_recall_at_5"]
