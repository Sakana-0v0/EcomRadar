"""A/B Framework 单元测试.

A/B 对比: 用同一 benchmark 跑两个版本 (A / B), 对比指标.
"""
import pytest
from pathlib import Path

from app.services.eval.ab_framework import (
    ABFramework,
    ABComparison,
    format_diff_report,
)


@pytest.fixture
def sample_dataset(tmp_path):
    path = tmp_path / "bench.jsonl"
    path.write_text(
        '{"id": "q1", "query": "x", "expected_answer": "y"}\n'
        '{"id": "q2", "query": "a", "expected_answer": "b"}\n',
        encoding="utf-8",
    )
    return path


class TestABComparison:
    def test_to_dict(self):
        comparison = ABComparison(
            variant_a="v1",
            variant_b="v2",
            metric_diffs={"exact_match": 0.05, "f1_score": 0.10},
        )
        d = comparison.to_dict()
        assert d["variant_a"] == "v1"
        assert d["variant_b"] == "v2"
        assert d["metric_diffs"]["exact_match"] == 0.05

    def test_to_markdown(self):
        comparison = ABComparison(
            variant_a="v1",
            variant_b="v2",
            metric_diffs={"exact_match": 0.05, "f1_score": 0.10, "latency_p50": -200},
        )
        md = comparison.to_markdown()
        assert "v1" in md
        assert "v2" in md
        assert "exact_match" in md


class TestABFramework:
    @pytest.mark.asyncio
    async def test_compare_two_variants(self, sample_dataset):
        async def predict_a(query: str) -> str:
            return "y" if query == "x" else "wrong"

        async def predict_b(query: str) -> str:
            return "y" if query == "x" else "b"

        framework = ABFramework(
            dataset_path=sample_dataset,
            variant_a_name="v1_baseline",
            predict_a=predict_a,
            variant_b_name="v2_improved",
            predict_b=predict_b,
        )
        comparison = await framework.compare()
        assert isinstance(comparison, ABComparison)
        assert comparison.variant_a == "v1_baseline"
        assert comparison.variant_b == "v2_improved"
        assert "exact_match" in comparison.metric_diffs


class TestFormatDiffReport:
    def test_format_basic(self):
        diffs = {"exact_match": 0.05, "f1_score": 0.10}
        md = format_diff_report(diffs, "v1", "v2")
        assert "v1" in md
        assert "v2" in md
        assert "+0.0500" in md or "0.05" in md
