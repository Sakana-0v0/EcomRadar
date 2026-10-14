"""Benchmark Runner - 端到端评测执行器.

数据流:
1. 加载 jsonl 数据集
2. 对每条数据调用 predict_fn (用户实现)
3. 记录延迟 + 计算 EM/F1
4. 汇总为 BenchmarkReport

设计取舍:
- predict_fn 是用户注入的 async 函数, 灵活适配各种场景
- 不绑定特定 Agent 框架
- 输出 jsonl 详细结果 + Markdown 报告
"""
import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Awaitable, Callable, Optional, Union

from app.services.eval.metrics import (
    exact_match,
    f1_score,
    rouge_l_score,
    compute_latency_stats,
    LatencyStats,
    MetricResult,
)


PredictFn = Callable[[str], Awaitable[str]]


@dataclass
class BenchmarkItem:
    """单条 benchmark 数据."""
    id: str
    query: str
    expected_answer: str
    category: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """单条预测结果."""
    item_id: str
    query: str
    expected: str
    prediction: str
    em: bool
    f1: float
    rouge_l: float
    latency_ms: float
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BenchmarkReport:
    """汇总报告."""
    dataset_name: str
    total_items: int
    metrics: list[MetricResult] = field(default_factory=list)
    results: list[BenchmarkResult] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "dataset_name": self.dataset_name,
            "total_items": self.total_items,
            "metrics": [m.to_dict() for m in self.metrics],
            "results": [r.to_dict() for r in self.results],
            "timestamp": self.timestamp,
        }

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# Benchmark Report: {self.dataset_name}")
        lines.append("")
        lines.append(f"**Total items**: {self.total_items}")
        lines.append(f"**Timestamp**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.timestamp))}")
        lines.append("")
        lines.append("## 核心指标")
        lines.append("")
        lines.append("| 指标 | 值 | 样本数 |")
        lines.append("|------|-----|--------|")
        for m in self.metrics:
            lines.append(f"| {m.name} | {m.value:.4f} | {m.count} |")
        lines.append("")
        return "\n".join(lines)


def load_benchmark(path: Union[str, Path]) -> list[BenchmarkItem]:
    """加载 jsonl 格式的 benchmark 数据集."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"benchmark file not found: {path}")
    items: list[BenchmarkItem] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        items.append(BenchmarkItem(
            id=data["id"],
            query=data["query"],
            expected_answer=data.get("expected_answer", ""),
            category=data.get("category", ""),
            metadata={k: v for k, v in data.items() if k not in ("id", "query", "expected_answer", "category")},
        ))
    return items


class BenchmarkRunner:
    """Benchmark 端到端执行器."""

    def __init__(
        self,
        dataset_path: Union[str, Path],
        predict_fn: PredictFn,
        dataset_name: Optional[str] = None,
        use_rouge_l: bool = True,
    ):
        self.dataset_path = Path(dataset_path)
        self.predict_fn = predict_fn
        self.dataset_name = dataset_name or self.dataset_path.stem
        self.use_rouge_l = use_rouge_l

    async def run(self) -> BenchmarkReport:
        """执行全部 benchmark."""
        items = load_benchmark(self.dataset_path)
        results: list[BenchmarkResult] = []
        latencies: list[float] = []

        for item in items:
            start = time.monotonic()
            prediction = ""
            error: Optional[str] = None
            try:
                prediction = await self.predict_fn(item.query)
            except Exception as e:
                error = f"{type(e).__name__}: {e}"
            elapsed_ms = (time.monotonic() - start) * 1000
            latencies.append(elapsed_ms)

            em = exact_match(prediction, item.expected_answer)
            f1 = f1_score(prediction, item.expected_answer)
            rouge = rouge_l_score(prediction, item.expected_answer) if self.use_rouge_l else 0.0

            results.append(BenchmarkResult(
                item_id=item.id,
                query=item.query,
                expected=item.expected_answer,
                prediction=prediction,
                em=em,
                f1=f1,
                rouge_l=rouge,
                latency_ms=elapsed_ms,
                error=error,
            ))

        metrics = self._aggregate_metrics(results, latencies)
        return BenchmarkReport(
            dataset_name=self.dataset_name,
            total_items=len(items),
            metrics=metrics,
            results=results,
        )

    def _aggregate_metrics(
        self,
        results: list[BenchmarkResult],
        latencies: list[float],
    ) -> list[MetricResult]:
        """汇总指标."""
        n = len(results)
        if n == 0:
            return []
        em_count = sum(1 for r in results if r.em)
        avg_f1 = sum(r.f1 for r in results) / n
        avg_rouge = sum(r.rouge_l for r in results) / n if self.use_rouge_l else 0.0
        latency_stats = compute_latency_stats(latencies)
        error_count = sum(1 for r in results if r.error)
        return [
            MetricResult(name="exact_match", value=em_count / n, count=n),
            MetricResult(name="f1_score", value=avg_f1, count=n),
            MetricResult(name="rouge_l", value=avg_rouge, count=n, metadata={} if not self.use_rouge_l else {}),
            MetricResult(
                name="latency",
                value=latency_stats.p50,
                count=latency_stats.count,
                metadata={
                    "p50": latency_stats.p50,
                    "p95": latency_stats.p95,
                    "mean": latency_stats.mean,
                    "min": latency_stats.min,
                    "max": latency_stats.max,
                },
            ),
            MetricResult(
                name="tool_call_success",
                value=(n - error_count) / n if n > 0 else 0,
                count=n,
                metadata={"errors": error_count},
            ),
        ]
