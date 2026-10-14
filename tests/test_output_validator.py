"""OutputValidator Pydantic 校验单元测试.

验证 Agent 输出是否符合 Schema:
- 报告 (Markdown) → 必须含指定章节
- 提取的竞品 (list[dict]) → 字段完整性
- 价格历史 → 数据格式
"""
import pytest
from pydantic import BaseModel, Field
from typing import Optional

from app.services.governance.output_validator import (
    OutputValidator,
    ValidationResult,
    MarkdownSectionRule,
    RequiredFieldRule,
)


class SampleProduct(BaseModel):
    name: str
    price: float = Field(gt=0)


class TestMarkdownSectionRule:
    def test_present_section_passes(self):
        rule = MarkdownSectionRule("Executive Summary")
        result = rule.check("# 标题\n## Executive Summary\n内容")
        assert result.passed is True

    def test_missing_section_fails(self):
        rule = MarkdownSectionRule("Executive Summary")
        result = rule.check("# 标题\n## 摘要\n内容")
        assert result.passed is False

    def test_case_insensitive(self):
        rule = MarkdownSectionRule("Executive Summary")
        result = rule.check("## executive summary")
        assert result.passed is True


class TestRequiredFieldRule:
    def test_field_present_passes(self):
        rule = RequiredFieldRule(["title", "price"])
        result = rule.check({"title": "x", "price": 100})
        assert result.passed is True

    def test_field_missing_fails(self):
        rule = RequiredFieldRule(["title", "price"])
        result = rule.check({"title": "x"})
        assert result.passed is False


class TestOutputValidator:
    def test_valid_passes(self):
        validator = OutputValidator(
            required_sections=["Executive Summary", "价格", "建议"],
        )
        result = validator.validate_report(
            "# 报告\n## Executive Summary\n## 价格\n## 建议\n",
        )
        assert result.passed is True

    def test_missing_sections_fails(self):
        validator = OutputValidator()
        result = validator.validate_report("# 报告\n")
        assert result.passed is False
        assert "Executive Summary" in result.missing

    def test_with_custom_rules(self):
        validator = OutputValidator(
            required_sections=["Executive Summary", "竞品矩阵", "行动建议"],
        )
        md = "# 报告\n## Executive Summary\n## 竞品矩阵\n## 行动建议"
        result = validator.validate_report(md)
        assert result.passed is True

    def test_validates_product_dict(self):
        validator = OutputValidator()
        result = validator.validate_product_list(
            [
                {"title": "商品A", "price": 100, "platform": "jd"},
                {"title": "商品B", "price": 200, "platform": "tmall"},
            ],
        )
        assert result.passed is True

    def test_rejects_empty_product_list(self):
        validator = OutputValidator()
        result = validator.validate_product_list([])
        assert result.passed is False

    def test_validates_pydantic_model(self):
        validator = OutputValidator()
        result = validator.validate_model(
            {"name": "test", "price": 99.0},
            SampleProduct,
        )
        assert result.passed is True

    def test_validates_pydantic_model_with_invalid_data(self):
        validator = OutputValidator()
        result = validator.validate_model(
            {"name": "test", "price": -1.0},
            SampleProduct,
        )
        assert result.passed is False
        assert "price" in str(result.errors).lower()

    def test_retry_suggestion_on_validation_failure(self):
        validator = OutputValidator()
        result = validator.validate_report("## 内容")
        assert result.passed is False
        assert result.should_retry is True
        assert "missing" in result.retry_hint.lower()


class TestValidationResult:
    def test_result_serializable(self):
        result = ValidationResult(
            passed=True,
            errors=[],
            missing=[],
        )
        d = result.to_dict()
        assert d["passed"] is True
        assert d["errors"] == []

    def test_result_with_errors(self):
        result = ValidationResult(
            passed=False,
            errors=["field 'price' missing"],
            missing=["Executive Summary"],
            should_retry=True,
            retry_hint="add Executive Summary section",
        )
        d = result.to_dict()
        assert d["passed"] is False
        assert d["should_retry"] is True
        assert "Executive Summary" in d["missing"]
