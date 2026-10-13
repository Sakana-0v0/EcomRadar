"""竞品报告 Pydantic Schema 单元测试."""
import pytest
from pydantic import ValidationError

from app.schemas.ecom_report import (
    CompetitorEntry,
    PriceChange,
    ActionItem,
    CompetitorReport,
    ReportSection,
)


class TestCompetitorEntry:
    def test_valid_entry(self):
        entry = CompetitorEntry(
            brand="小度",
            platform="jd",
            price=329.0,
            sales="5万+",
            dsr=4.8,
            key_action="新增户外 SKU",
        )
        assert entry.brand == "小度"
        assert entry.price == 329.0

    def test_price_must_be_positive(self):
        with pytest.raises(ValidationError):
            CompetitorEntry(brand="x", platform="jd", price=-1)

    def test_optional_fields_have_defaults(self):
        entry = CompetitorEntry(brand="x", platform="jd", price=100.0)
        assert entry.sales == ""
        assert entry.dsr is None
        assert entry.key_action == ""

    def test_brand_required(self):
        with pytest.raises(ValidationError):
            CompetitorEntry(brand="", platform="jd", price=100.0)


class TestPriceChange:
    def test_valid_change(self):
        change = PriceChange(
            brand="天猫精灵",
            old_price=299.0,
            new_price=263.0,
            change_pct=-12.0,
        )
        assert change.change_pct == -12.0

    def test_change_pct_can_be_positive(self):
        change = PriceChange(brand="x", old_price=100, new_price=110, change_pct=10.0)
        assert change.change_pct == 10.0

    def test_brand_required(self):
        with pytest.raises(ValidationError):
            PriceChange(brand="", old_price=100, new_price=110, change_pct=10.0)


class TestActionItem:
    def test_valid_action(self):
        action = ActionItem(
            priority=1,
            title="错位定价",
            description="在 ¥299~¥399 价格带做音质升级差异化",
        )
        assert action.priority == 1
        assert action.title

    def test_priority_range_1_to_5(self):
        with pytest.raises(ValidationError):
            ActionItem(priority=0, title="x", description="y")
        with pytest.raises(ValidationError):
            ActionItem(priority=6, title="x", description="y")


class TestCompetitorReport:
    def test_valid_full_report(self):
        report = CompetitorReport(
            category="智能音箱",
            period="2026-W42",
            executive_summary="本周天猫精灵降价 12%",
            competitor_matrix=[
                CompetitorEntry(brand="小度", platform="jd", price=329.0),
                CompetitorEntry(brand="天猫精灵", platform="tmall", price=263.0),
            ],
            price_changes=[
                PriceChange(brand="天猫精灵", old_price=299.0, new_price=263.0, change_pct=-12.0),
            ],
            action_items=[
                ActionItem(priority=1, title="错位定价", description="..."),
            ],
        )
        assert report.category == "智能音箱"
        assert len(report.competitor_matrix) == 2
        assert len(report.price_changes) == 1
        assert len(report.action_items) == 1

    def test_to_markdown_includes_all_sections(self):
        report = CompetitorReport(
            category="智能音箱",
            period="2026-W42",
            executive_summary="本周动态",
            competitor_matrix=[
                CompetitorEntry(brand="小度", platform="jd", price=329.0, dsr=4.8),
            ],
            price_changes=[
                PriceChange(brand="天猫精灵", old_price=299.0, new_price=263.0, change_pct=-12.0),
            ],
            action_items=[
                ActionItem(priority=1, title="错位定价", description="错位竞争"),
            ],
        )
        md = report.to_markdown()
        assert "# 竞品周报 - 智能音箱" in md
        assert "## Executive Summary" in md
        assert "## 竞品矩阵对比" in md
        assert "## 价格波动分析" in md
        assert "## 行动建议" in md
        assert "小度" in md
        assert "-12" in md
        assert "错位定价" in md

    def test_to_markdown_contains_comparison_table(self):
        report = CompetitorReport(
            category="美妆口红",
            period="2026-09",
            executive_summary="月报",
            competitor_matrix=[
                CompetitorEntry(brand="完美日记", platform="tmall", price=129.0),
                CompetitorEntry(brand="花西子", platform="tmall", price=219.0),
            ],
        )
        md = report.to_markdown()
        assert "| 品牌 |" in md
        assert "完美日记" in md
        assert "花西子" in md

    def test_minimal_report_still_valid(self):
        report = CompetitorReport(
            category="测试",
            period="2026-W01",
            executive_summary="无",
        )
        assert report.competitor_matrix == []
        assert report.price_changes == []
        assert report.action_items == []
        md = report.to_markdown()
        assert "# 竞品周报" in md


class TestReportSection:
    def test_section_creation(self):
        section = ReportSection(
            heading="Executive Summary",
            content="本周动态",
        )
        assert section.heading == "Executive Summary"
        assert section.content == "本周动态"
