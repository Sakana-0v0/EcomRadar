"""评测指标单元测试.

核心指标:
- exact_match (EM): 答案完全匹配(归一化后)
- f1_score: 字符级 F1 (适合中文)
- tool_call_success_rate: 工具调用成功率
- latency_percentile: P50/P95 延迟
- rouge_l: 摘要类任务
"""
import pytest

from app.services.eval.metrics import (
    exact_match,
    f1_score,
    tokenize_for_f1,
    compute_latency_stats,
    rouge_l_score,
    MetricResult,
)


class TestExactMatch:
    def test_identical_strings(self):
        assert exact_match("hello", "hello") is True

    def test_case_insensitive(self):
        assert exact_match("Hello", "hello") is True

    def test_whitespace_normalized(self):
        assert exact_match("  hello  world  ", "hello world") is True

    def test_punctuation_stripped(self):
        assert exact_match("Hello, world!", "hello world") is True

    def test_different_strings(self):
        assert exact_match("hello", "world") is False

    def test_empty_strings(self):
        assert exact_match("", "") is True
        assert exact_match("", "x") is False
        assert exact_match("x", "") is False

    def test_chinese_normalization(self):
        assert exact_match("  小度智能音箱  ", "小度智能音箱") is True


class TestF1Score:
    def test_identical_strings(self):
        assert f1_score("hello world", "hello world") == 1.0

    def test_no_overlap(self):
        assert f1_score("abc", "xyz") == 0.0

    def test_partial_overlap(self):
        s = f1_score("小度智能音箱", "小度音箱")
        assert 0 < s < 1

    def test_empty_strings(self):
        assert f1_score("", "hello") == 0.0
        assert f1_score("hello", "") == 0.0
        assert f1_score("", "") == 0.0

    def test_substring_match(self):
        s = f1_score("小度智能音箱蓝牙版", "小度智能音箱")
        assert s > 0.7


class TestTokenizeForF1:
    def test_chinese_bigrams(self):
        """2-gram 切分: 适合中文短语."""
        tokens = tokenize_for_f1("小度智能音箱")
        assert "小度" in tokens
        assert "智能" in tokens
        assert "音箱" in tokens

    def test_english_words(self):
        tokens = tokenize_for_f1("iPhone 15 Pro")
        assert "iphone" in tokens
        assert "15" in tokens

    def test_mixed(self):
        tokens = tokenize_for_f1("iPhone 15 智能版")
        assert "iphone" in tokens
        assert "15" in tokens
        assert "智能" in tokens


class TestComputeLatencyStats:
    def test_empty_returns_zeros(self):
        stats = compute_latency_stats([])
        assert stats.count == 0
        assert stats.p50 == 0.0
        assert stats.p95 == 0.0

    def test_single_value(self):
        stats = compute_latency_stats([100.0])
        assert stats.count == 1
        assert stats.p50 == 100.0
        assert stats.p95 == 100.0

    def test_percentiles(self):
        stats = compute_latency_stats([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
        assert stats.count == 10
        assert stats.min == 10.0
        assert stats.max == 100.0
        assert stats.mean == 55.0
        # p50: 偶数长度, 取两个中位平均 = (50+60)/2 = 55
        assert stats.p50 == 55.0
        # p95: 线性插值, k=8.55, f=8 (90), c=9 (100), 值=95.5
        assert stats.p95 == pytest.approx(95.5, abs=0.1)

    def test_handles_unsorted(self):
        stats = compute_latency_stats([100, 10, 50, 30, 70])
        assert stats.min == 10.0
        assert stats.max == 100.0
        assert stats.median == 50.0


class TestRougeL:
    def test_identical(self):
        assert rouge_l_score("hello world", "hello world") == 1.0

    def test_no_overlap(self):
        assert rouge_l_score("abc def", "xyz uvw") == 0.0

    def test_partial(self):
        s = rouge_l_score("小度智能音箱旗舰版", "小度智能音箱")
        assert 0 < s < 1


class TestMetricResult:
    def test_to_dict(self):
        r = MetricResult(name="em", value=0.85, count=100, metadata={"extra": "info"})
        d = r.to_dict()
        assert d["name"] == "em"
        assert d["value"] == 0.85
        assert d["count"] == 100
