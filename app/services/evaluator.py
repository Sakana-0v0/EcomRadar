"""Evaluator v2 - 5 维度电商报告评分.

维度权重:
- 事实忠实度 25%   (含核心要点/摘要关键词)
- 结构完整性 25%   (Markdown 标题层级)
- 价格对比完整性 20% (含价格数字 / 对比表)
- SKU 覆盖度 15%   (提及 SKU 规格)
- 行动建议质量 15% (含"建议""行动"等关键词)

设计取舍:
- 纯规则评分,不调 LLM(速度快、可解释、零成本)
- Phase 8 评测体系阶段会引入 LLM-as-Judge 作对照
"""
import re
from dataclasses import dataclass, field, asdict
from typing import Optional


THRESHOLD_PASS: int = 75

DIMENSION_WEIGHTS: dict[str, float] = {
    "factuality": 0.25,
    "structure": 0.25,
    "price_comparison": 0.20,
    "sku_coverage": 0.15,
    "action_quality": 0.15,
}


@dataclass
class EvaluationResult:
    """单次评分结果."""
    score: int
    passed: bool
    dimensions: dict[str, float] = field(default_factory=dict)
    missing_sections: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _score_factuality(report: str) -> float:
    """事实忠实度:含摘要/核心要点关键词."""
    if not report:
        return 0.0
    keywords = ["摘要", "总结", "核心", "要点", "Executive Summary", "summary"]
    hits = sum(1 for kw in keywords if kw.lower() in report.lower())
    return min(1.0, hits / 2)


def _score_structure(report: str) -> float:
    """结构完整性:Markdown 标题层级 + 必要分节."""
    if not report:
        return 0.0
    h1_count = len(re.findall(r"^#\s+\S+", report, re.MULTILINE))
    h2_count = len(re.findall(r"^##\s+\S+", report, re.MULTILINE))
    if h1_count >= 1 and h2_count >= 3:
        return 1.0
    if h1_count >= 1 and h2_count >= 1:
        return 0.7
    if h2_count >= 2:
        return 0.5
    if h1_count >= 1 or h2_count >= 1:
        return 0.3
    return 0.0


def _score_price_comparison(report: str) -> float:
    """价格对比完整性:含价格数字 + 对比表."""
    if not report:
        return 0.0
    has_table = "| 价格" in report or "| price" in report.lower() or "| 品牌" in report
    price_count = len(re.findall(r"[¥￥]\s*\d+", report))
    has_change = bool(re.search(r"[-+]?\s*\d+\.?\d*\s*%", report))

    score = 0.0
    if has_table:
        score += 0.5
    if price_count >= 2:
        score += 0.3
    if has_change:
        score += 0.2
    return min(1.0, score)


def _score_sku_coverage(report: str) -> float:
    """SKU 覆盖度:提及 SKU/规格."""
    if not report:
        return 0.0
    has_sku_kw = bool(re.search(r"SKU|规格|颜色|尺码", report))
    has_sku_data = bool(re.search(r"\d+\s*种\s*SKU|共\s*\d+\s*规格", report))
    has_sku_table = bool(re.search(r"\|.*SKU.*\|", report, re.IGNORECASE))

    score = 0.0
    if has_sku_kw:
        score += 0.4
    if has_sku_data:
        score += 0.3
    if has_sku_table:
        score += 0.3
    return min(1.0, score)


def _score_action_quality(report: str) -> float:
    """行动建议质量:含建议/行动关键词 + 编号列表."""
    if not report:
        return 0.0
    has_action_kw = bool(re.search(r"建议|行动|策略|打法|action|recommend", report, re.IGNORECASE))
    has_numbered = bool(re.search(r"\*\*\d+\.\s+\S+", report))
    has_specific = bool(re.search(r"价格带|SKU|大促|百亿补贴|满减", report))

    score = 0.0
    if has_action_kw:
        score += 0.4
    if has_numbered:
        score += 0.3
    if has_specific:
        score += 0.3
    return min(1.0, score)


def evaluate_competitor_report(report: str) -> EvaluationResult:
    """5 维度评分,返回结构化结果.

    Args:
        report: Markdown 报告文本

    Returns:
        EvaluationResult 含 score / passed / dimensions / missing_sections
    """
    if not report:
        return EvaluationResult(
            score=0,
            passed=False,
            dimensions={k: 0.0 for k in DIMENSION_WEIGHTS},
            missing_sections=["all"],
            notes=["empty report"],
        )

    dimensions = {
        "factuality": _score_factuality(report),
        "structure": _score_structure(report),
        "price_comparison": _score_price_comparison(report),
        "sku_coverage": _score_sku_coverage(report),
        "action_quality": _score_action_quality(report),
    }

    score_raw = sum(dimensions[k] * DIMENSION_WEIGHTS[k] for k in DIMENSION_WEIGHTS)
    score = int(round(score_raw * 100))

    missing = []
    if dimensions["factuality"] < 0.5:
        missing.append("executive_summary")
    if dimensions["structure"] < 0.5:
        missing.append("structure")
    if dimensions["price_comparison"] < 0.5:
        missing.append("price_comparison")
    if dimensions["sku_coverage"] < 0.3:
        missing.append("sku_coverage")
    if dimensions["action_quality"] < 0.5:
        missing.append("action_items")

    notes = []
    if score < THRESHOLD_PASS:
        notes.append(f"below threshold ({THRESHOLD_PASS}), consider retry")
    if missing:
        notes.append(f"missing sections: {', '.join(missing)}")

    return EvaluationResult(
        score=score,
        passed=score >= THRESHOLD_PASS,
        dimensions=dimensions,
        missing_sections=missing,
        notes=notes,
    )


def evaluate_report(report: str) -> int:
    """原 evaluate_report - 兼容旧调用,只返回 0~100 整数.

    委托给 evaluate_competitor_report 取 score 字段.
    """
    if not report:
        return 0
    has_summary = bool(re.search(r"摘要|总结|核心|要点", report))
    has_structure = bool(re.search(r"##\s+\w+", report))
    has_content = len(report) > 100
    score = 0
    score += 40 if has_summary else 20
    score += 30 if has_structure else 15
    score += 30 if has_content else 10
    return min(100, max(0, score))
