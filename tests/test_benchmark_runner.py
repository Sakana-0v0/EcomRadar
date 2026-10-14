"""BenchmarkRunner 单元测试.

端到端评测 Runner:
- 加载 benchmark jsonl 数据集
- 调用 predict_fn (用户实现)
- 收集结果 (EM/F1/Latency)
- 输出 BenchmarkReport
"""
import json
import time
import pytest
from pathlib import Path

from app.services.eval.runner import (
    BenchmarkRunner,
    BenchmarkItem,
    BenchmarkResult,
    BenchmarkReport,
    load_benchmark,
)


SAMPLE_JSONL = """\
{"id": "q1", "query": "小度智能音箱价格", "expected_answer": "329元", "category": "价格"}
{"id": "q2", "query": "口红价格带", "expected_answer": "100-300元", "category": "价格"}
{"id": "q3", "query": "双11节奏", "expected_answer": "11月11日高峰", "category": "营销"}
"""


@pytest.fixture
def sample_dataset(tmp_path):
    path = tmp_path / "test_bench.jsonl"
    path.write_text(SAMPLE_JSONL, encoding="utf-8")
    return path


class TestLoadBenchmark:
    def test_load_from_file(self, sample_dataset):
        items = load_benchmark(sample_dataset)
        assert len(items) == 3
        assert items[0].id == "q1"
        assert items[0].expected_answer == "329元"

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_benchmark(tmp_path / "nonexistent.jsonl")

    def test_load_empty_file(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        items = load_benchmark(path)
        assert items == []

    def test_load_skips_blank_lines(self, tmp_path):
        path = tmp_path / "blank_lines.jsonl"
        path.write_text(
            '{"id": "q1", "query": "x", "expected_answer": "y"}\n\n\n',
            encoding="utf-8",
        )
        items = load_benchmark(path)
        assert len(items) == 1


class TestBenchmarkRunner:
    @pytest.mark.asyncio
    async def test_runs_all_items(self, sample_dataset):
        async def predict(query: str) -> str:
            return {"小度智能音箱价格": "329元", "口红价格带": "100-300元", "双11节奏": "11月11日高峰"}.get(query, "")

        runner = BenchmarkRunner(
            dataset_path=sample_dataset,
            predict_fn=predict,
        )
        report = await runner.run()
        assert report.total_items == 3
        assert len(report.results) == 3

    @pytest.mark.asyncio
    async def test_computes_em_metric(self, sample_dataset):
        async def predict(query: str) -> str:
            return {"小度智能音箱价格": "329元", "口红价格带": "100-300元", "双11节奏": "wrong"}[query]

        runner = BenchmarkRunner(dataset_path=sample_dataset, predict_fn=predict)
        report = await runner.run()
        em = next(m for m in report.metrics if m.name == "exact_match")
        assert em.value == pytest.approx(2 / 3, abs=0.01)

    @pytest.mark.asyncio
    async def test_computes_f1_metric(self, sample_dataset):
        async def predict(query: str) -> str:
            return {"小度智能音箱价格": "329", "口红价格带": "100-300", "双11节奏": "完全错误"}[query]

        runner = BenchmarkRunner(dataset_path=sample_dataset, predict_fn=predict)
        report = await runner.run()
        f1 = next(m for m in report.metrics if m.name == "f1_score")
        assert 0 < f1.value < 1

    @pytest.mark.asyncio
    async def test_measures_latency(self, sample_dataset):
        async def predict(query: str) -> str:
            await asyncio_sleep(0.01)
            return "x"

        import asyncio
        async def asyncio_sleep(s):
            await asyncio.sleep(s)

        runner = BenchmarkRunner(dataset_path=sample_dataset, predict_fn=predict)
        report = await runner.run()
        latency = next(m for m in report.metrics if m.name == "latency")
        assert latency.metadata["p50"] >= 10
        assert latency.count == 3

    @pytest.mark.asyncio
    async def test_records_per_item_results(self, sample_dataset):
        async def predict(query: str) -> str:
            return "329元" if "价格" in query else "其他"

        runner = BenchmarkRunner(dataset_path=sample_dataset, predict_fn=predict)
        report = await runner.run()
        assert all(isinstance(r, BenchmarkResult) for r in report.results)
        assert all(hasattr(r, "latency_ms") for r in report.results)


class TestBenchmarkReport:
    def test_to_dict(self):
        report = BenchmarkReport(
            dataset_name="test",
            total_items=10,
            metrics=[],
            results=[],
        )
        d = report.to_dict()
        assert d["total_items"] == 10
        assert d["dataset_name"] == "test"
        assert "metrics" in d

    def test_to_markdown(self):
        report = BenchmarkReport(
            dataset_name="test",
            total_items=10,
            metrics=[],
            results=[],
        )
        md = report.to_markdown()
        assert "# Benchmark Report" in md
        assert "test" in md
