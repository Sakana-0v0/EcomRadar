"""A/B Testing 框架 - 同一数据集上对比两个版本.

典型用法:
- 对比 prompt_v1 vs prompt_v2
- 对比 gpt-4 vs claude-sonnet
- 对比 Rerank 开启 vs 关闭

输出:
- ABComparison 数据类 (每个指标的 diff)
- Markdown 对比报告
"""
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Awaitable, Callable, Union

from app.services.eval.runner import BenchmarkRunner, PredictFn


@dataclass
class ABComparison:
    """A/B 对比结果."""
    variant_a: str
    variant_b: str
    metric_diffs: dict = field(default_factory=dict)
    metrics_a: dict = field(default_factory=dict)
    metrics_b: dict = field(default_factory=dict)
    winner: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = [
            f"# A/B Comparison: {self.variant_a} vs {self.variant_b}",
            "",
            f"**Winner**: {self.winner or '(no clear winner)'}",
            "",
            "## 指标对比",
            "",
            "| 指标 | A | B | Diff (B-A) |",
            "|------|---|---|------------|",
        ]
        for name, diff in self.metric_diffs.items():
            a_val = self.metrics_a.get(name, 0)
            b_val = self.metrics_b.get(name, 0)
            sign = "+" if diff >= 0 else ""
            lines.append(f"| {name} | {a_val:.4f} | {b_val:.4f} | {sign}{diff:.4f} |")
        lines.append("")
        return "\n".join(lines)


class ABFramework:
    """A/B 对比执行器."""

    def __init__(
        self,
        dataset_path: Union[str, Path],
        variant_a_name: str,
        predict_a: PredictFn,
        variant_b_name: str,
        predict_b: PredictFn,
    ):
        self.dataset_path = Path(dataset_path)
        self.variant_a_name = variant_a_name
        self.variant_b_name = variant_b_name
        self.predict_a = predict_a
        self.predict_b = predict_b

    async def compare(self) -> ABComparison:
        """跑 A/B 两个版本, 对比指标."""
        runner_a = BenchmarkRunner(
            dataset_path=self.dataset_path,
            predict_fn=self.predict_a,
            dataset_name=self.variant_a_name,
        )
        runner_b = BenchmarkRunner(
            dataset_path=self.dataset_path,
            predict_fn=self.predict_b,
            dataset_name=self.variant_b_name,
        )
        report_a = await runner_a.run()
        report_b = await runner_b.run()

        metrics_a = {m.name: m.value for m in report_a.metrics}
        metrics_b = {m.name: m.value for m in report_b.metrics}

        all_keys = set(metrics_a.keys()) | set(metrics_b.keys())
        diffs: dict[str, float] = {}
        for key in all_keys:
            a = metrics_a.get(key, 0)
            b = metrics_b.get(key, 0)
            diffs[key] = b - a

        winner = self._decide_winner(metrics_a, metrics_b)
        return ABComparison(
            variant_a=self.variant_a_name,
            variant_b=self.variant_b_name,
            metric_diffs=diffs,
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            winner=winner,
        )

    @staticmethod
    def _decide_winner(metrics_a: dict, metrics_b: dict) -> str:
        """根据核心指标决定胜方 (EM/F1 优先)."""
        score = 0.0
        for key in ("exact_match", "f1_score"):
            diff = metrics_b.get(key, 0) - metrics_a.get(key, 0)
            score += diff
        if score > 0.01:
            return "B"
        if score < -0.01:
            return "A"
        return ""


def format_diff_report(
    diffs: dict,
    name_a: str,
    name_b: str,
) -> str:
    """格式化 diff 报告."""
    lines = [f"# Diff: {name_a} → {name_b}", ""]
    for key, value in diffs.items():
        sign = "+" if value >= 0 else ""
        lines.append(f"- **{key}**: {sign}{value:.4f}")
    return "\n".join(lines)
