"""Evaluator v2 单元测试 (多维度电商评分).

5 维度评分 (满分 100):
- 事实忠实度 25%
- 结构完整性 25%
- 价格对比完整性 20%
- SKU 覆盖度 15%
- 行动建议质量 15%
"""
import pytest

from app.services.evaluator import (
    evaluate_report,
    evaluate_competitor_report,
    EvaluationResult,
    DIMENSION_WEIGHTS,
    THRESHOLD_PASS,
)


class TestEvaluateReportLegacy:
    """原 evaluate_report 行为兼容测试."""

    def test_empty_report_zero_score(self):
        assert evaluate_report("") == 0

    def test_basic_report_above_threshold(self):
        report = "# 标题\n## 核心要点\n详细内容..."
        score = evaluate_report(report)
        assert score >= THRESHOLD_PASS

    def test_short_report_below_threshold(self):
        report = "abc"
        score = evaluate_report(report)
        assert score < THRESHOLD_PASS


class TestEvaluateCompetitorReport:
    """新 evaluate_competitor_report 多维度评分测试."""

    def test_returns_evaluation_result(self):
        result = evaluate_competitor_report("任何文本")
        assert isinstance(result, EvaluationResult)
        assert 0 <= result.score <= 100

    def test_excellent_report_above_threshold(self):
        """优秀报告:含表格 + 价格 + 建议 + 标题结构."""
        report = """
# 竞品周报 - 智能音箱

**周期**: 2026-W42

## Executive Summary

本周天猫精灵下调主力款售价 12% (从 ¥299 → ¥263),小度新增
"户外便携"SKU 抢占细分市场,小爱同学差评率上升 3pp。建议
本周内做"音质升级"内容营销。

## 竞品矩阵对比

| 品牌 | 平台 | 价格 | 销量 | DSR | 关键动作 |
|------|------|------|------|-----|----------|
| 天猫精灵 | tmall | 263 | 8w+ | 4.9 | 大促降价 |
| 小度 | jd | 329 | 5w+ | 4.8 | 新增 SKU |
| 小爱 | jd | 349 | 3w+ | 4.6 | 联名款 |

## 价格波动分析

- 天猫精灵: ¥299 → ¥263 (-12%)

## 行动建议

**1. 错位定价** — 在 ¥299~¥399 价格带做"音质升级"差异化
**2. 内容种草** — 抖音/小红书打"蓝牙连接稳定性"实测
**3. SKU 策略** — 考虑新增 ¥499 户外便携 SKU
"""
        result = evaluate_competitor_report(report)
        assert result.score >= THRESHOLD_PASS
        assert result.passed is True
        assert result.dimensions["structure"] >= 0.8
        assert result.dimensions["price_comparison"] >= 0.8

    def test_poor_report_below_threshold(self):
        """劣质报告:无表格无价格无建议."""
        report = "随便写的一段话没有任何结构"
        result = evaluate_competitor_report(report)
        assert result.score < THRESHOLD_PASS
        assert result.passed is False

    def test_dimensions_sum_to_100(self):
        """所有维度权重之和为 100%."""
        assert abs(sum(DIMENSION_WEIGHTS.values()) - 1.0) < 0.001

    def test_partial_report_partial_score(self):
        """有部分维度的报告得部分分."""
        report = """
# 竞品周报

## Executive Summary

本周动态摘要...

## 竞品矩阵对比

| 品牌 | 价格 |
|------|------|
| A | 100 |
| B | 200 |
"""
        result = evaluate_competitor_report(report)
        assert 40 <= result.score <= 90, f"score={result.score}"


class TestEvaluationResult:
    """EvaluationResult 数据类测试."""

    def test_score_passed(self):
        result = EvaluationResult(score=85, passed=True, dimensions={}, missing_sections=[])
        assert result.passed is True
        assert result.score == 85

    def test_to_dict_serializes_all_fields(self):
        result = EvaluationResult(
            score=75,
            passed=True,
            dimensions={"structure": 0.8, "price_comparison": 0.7},
            missing_sections=[],
        )
        d = result.to_dict()
        assert d["score"] == 75
        assert d["passed"] is True
        assert d["dimensions"]["structure"] == 0.8
