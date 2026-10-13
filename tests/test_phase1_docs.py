"""Phase 1 验收测试: 业务预研文档必须存在并含关键章节."""
from pathlib import Path

import pytest

DOCS_DIR = Path(__file__).parent.parent / "docs"


def test_ecommerce_domain_notes_exists():
    """电商领域认知文档必须存在."""
    assert (DOCS_DIR / "ECOMMERCE_DOMAIN_NOTES.md").exists(), (
        "缺少 docs/ECOMMERCE_DOMAIN_NOTES.md"
    )


def test_ecommerce_domain_notes_has_7_concepts():
    """必须覆盖 7 大电商核心概念."""
    content = (DOCS_DIR / "ECOMMERCE_DOMAIN_NOTES.md").read_text(encoding="utf-8")

    required_concepts = [
        "商品详情页结构",
        "平台流量分发逻辑",
        "价格矩阵",
        "SKU 策略",
        "评价分析",
        "营销节点",
        "店铺健康度",
    ]
    for concept in required_concepts:
        assert concept in content, f"ECOMMERCE_DOMAIN_NOTES 缺少章节: {concept}"


def test_demo_scenarios_exists():
    """演示场景文档必须存在."""
    assert (DOCS_DIR / "DEMO_SCENARIOS.md").exists(), (
        "缺少 docs/DEMO_SCENARIOS.md"
    )


def test_demo_scenarios_has_three_scenarios():
    """必须包含至少 3 个虚构竞品监控场景."""
    content = (DOCS_DIR / "DEMO_SCENARIOS.md").read_text(encoding="utf-8")
    # 检查场景章节标题(以数字编号的 ## 标题)
    import re
    scenario_headers = re.findall(r"^##\s+(?:场景|Scenario)\s*\d+", content, re.MULTILINE)
    assert len(scenario_headers) >= 3, (
        f"DEMO_SCENARIOS 应至少 3 个场景,实际找到 {len(scenario_headers)} 个"
    )


def test_compliance_notes_exists():
    """合规说明文档必须存在."""
    assert (DOCS_DIR / "COMPLIANCE_NOTES.md").exists(), (
        "缺少 docs/COMPLIANCE_NOTES.md"
    )


def test_compliance_notes_has_required_items():
    """必须包含核心合规自检项."""
    content = (DOCS_DIR / "COMPLIANCE_NOTES.md").read_text(encoding="utf-8")
    required_items = [
        "robots.txt",
        "限速",
        "个人信息",
        "技术保护",
    ]
    for item in required_items:
        assert item in content, f"COMPLIANCE_NOTES 缺少关键项: {item}"


def test_phase1_docs_total_size_reasonable():
    """三个文档合计应超过 5000 字符(深度内容)."""
    files = [
        "ECOMMERCE_DOMAIN_NOTES.md",
        "DEMO_SCENARIOS.md",
        "COMPLIANCE_NOTES.md",
    ]
    total = sum(
        (DOCS_DIR / f).read_text(encoding="utf-8").__len__()
        for f in files
        if (DOCS_DIR / f).exists()
    )
    assert total > 5000, f"Phase 1 文档总字符数 {total},期望 > 5000"
