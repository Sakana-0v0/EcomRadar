"""端到端 Benchmark 运行脚本.

用法:
    python -m scripts.run_benchmark                              # 跑知识库检索 baseline
    python -m scripts.run_benchmark --variant=writer            # 跑 Writer 报告(需 LLM API)
    python -m scripts.run_benchmark --output=data/results_v1.json
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


def make_predict_fn(variant: str):
    """构造预测函数 (不同 variant 走不同链路)."""
    if variant == "retrieval":
        async def predict(query: str) -> str:
            from app.services.retrieval.bm25_index import BM25Index
            from app.services.retrieval.hybrid_search import HybridSearcher
            from app.services.embedding import embed_text

            kb = [
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
                {"id": "kb_011", "text": "完美日记主打性价比,核心价格带 89-129 元", "category": "美妆"},
                {"id": "kb_012", "text": "花西子主打国潮,核心价格带 199-299 元", "category": "美妆"},
                {"id": "kb_013", "text": "京东 PLUS 会员可享专属价,平均优惠 5-10%", "category": "平台活动"},
                {"id": "kb_014", "text": "天猫 88VIP 享 95 折,跨平台通用", "category": "平台活动"},
                {"id": "kb_015", "text": "短视频带货转化率比图文高 2-3 倍,完播率是关键指标", "category": "运营策略"},
            ]
            bm25 = BM25Index()
            bm25.add_documents(kb)
            searcher = HybridSearcher(bm25=bm25, embed_fn=embed_text, dense_weight=0.7)
            results = await searcher.search(query, top_k=1)
            return results[0]["text"] if results else ""

        return predict
    raise ValueError(f"unknown variant: {variant}")


async def run(variant: str, output: str, dataset: str) -> None:
    from app.services.eval.runner import BenchmarkRunner

    predict = make_predict_fn(variant)
    runner = BenchmarkRunner(
        dataset_path=dataset,
        predict_fn=predict,
        dataset_name=f"ecom_qa_{variant}",
    )
    report = await runner.run()
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Report saved: {out_path}")
    print()
    print(report.to_markdown())
    print()
    print("=== Per-Item Results (top 10) ===")
    for r in report.results[:10]:
        em_mark = "✓" if r.em else "✗"
        print(f"  {em_mark} [{r.item_id}] f1={r.f1:.2f} latency={r.latency_ms:.0f}ms".encode("utf-8", errors="replace").decode("utf-8"))
        print(f"      Q: {r.query}")
        print(f"      Expected: {r.expected[:60]}")
        print(f"      Got:      {r.prediction[:60]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="retrieval", choices=["retrieval", "writer"])
    parser.add_argument("--output", default="data/eval_results/latest.json")
    parser.add_argument("--dataset", default="data/benchmark/ecom_qa_v1.jsonl")
    args = parser.parse_args()

    import sys
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    asyncio.run(run(args.variant, args.output, args.dataset))


if __name__ == "__main__":
    main()
