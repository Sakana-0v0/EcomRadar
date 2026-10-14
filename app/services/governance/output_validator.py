"""Output Validator - Pydantic + Markdown 校验.

Agent 输出多种形式校验:
- Markdown 报告:必须含指定章节
- 提取的竞品列表:必填字段检查
- Pydantic Model:类型 + 约束校验

校验失败时:
- 标记 should_retry=True
- 生成 retry_hint 指导 LLM 改进
"""
import re
from dataclasses import dataclass, field, asdict
from typing import Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)


@dataclass
class ValidationResult:
    """单次校验结果."""
    passed: bool
    errors: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    should_retry: bool = False
    retry_hint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MarkdownSectionRule:
    """Markdown 必含章节规则."""
    section_name: str
    case_sensitive: bool = False

    def check(self, text: str) -> ValidationResult:
        pattern = re.escape(self.section_name)
        if not self.case_sensitive:
            flags = re.IGNORECASE
        else:
            flags = 0
        section_pattern = rf"^##\s+{pattern}\s*$"
        if re.search(section_pattern, text, flags=flags | re.MULTILINE):
            return ValidationResult(passed=True)
        return ValidationResult(
            passed=False,
            errors=[f"missing markdown section: {self.section_name}"],
            missing=[self.section_name],
            should_retry=True,
            retry_hint=f"add '## {self.section_name}' section to the report",
        )


@dataclass
class RequiredFieldRule:
    """必填字段规则."""
    fields: list[str]

    def check(self, data: dict) -> ValidationResult:
        missing = [f for f in self.fields if f not in data or data[f] is None]
        if not missing:
            return ValidationResult(passed=True)
        return ValidationResult(
            passed=False,
            errors=[f"missing required fields: {missing}"],
            missing=missing,
            should_retry=True,
            retry_hint=f"include fields: {', '.join(missing)}",
        )


class OutputValidator:
    """统一校验器.

    Args:
        required_sections: 报告必含 Markdown 章节
        required_product_fields: 商品字典必含字段
    """

    DEFAULT_SECTIONS = [
        "Executive Summary",
        "竞品矩阵",
        "价格",
        "行动建议",
    ]
    DEFAULT_PRODUCT_FIELDS = ["title", "price", "platform"]

    def __init__(
        self,
        required_sections: Optional[list[str]] = None,
        required_product_fields: Optional[list[str]] = None,
    ):
        self.required_sections = required_sections or self.DEFAULT_SECTIONS
        self.required_product_fields = required_product_fields or self.DEFAULT_PRODUCT_FIELDS

    def validate_report(self, report: str) -> ValidationResult:
        """校验 Markdown 报告."""
        if not report or not report.strip():
            return ValidationResult(
                passed=False,
                errors=["empty report"],
                missing=list(self.required_sections),
                should_retry=True,
                retry_hint="generate non-empty report with required sections",
            )

        all_missing: list[str] = []
        all_errors: list[str] = []
        for section in self.required_sections:
            rule = MarkdownSectionRule(section)
            result = rule.check(report)
            if not result.passed:
                all_missing.extend(result.missing)
                all_errors.extend(result.errors)

        if all_missing:
            return ValidationResult(
                passed=False,
                errors=all_errors,
                missing=all_missing,
                should_retry=True,
                retry_hint=f"add missing sections: {', '.join(all_missing)}",
            )
        return ValidationResult(passed=True)

    def validate_product_list(self, products: list[dict]) -> ValidationResult:
        """校验竞品列表."""
        if not products:
            return ValidationResult(
                passed=False,
                errors=["empty product list"],
                should_retry=False,
                retry_hint="scraper may have failed; check upstream",
            )

        rule = RequiredFieldRule(self.required_product_fields)
        all_errors: list[str] = []
        for i, product in enumerate(products):
            result = rule.check(product)
            if not result.passed:
                all_errors.append(f"product[{i}]: {result.errors}")

        if all_errors:
            return ValidationResult(
                passed=False,
                errors=all_errors,
                should_retry=False,
                retry_hint="fix data extraction at scraper level",
            )
        return ValidationResult(passed=True)

    def validate_model(self, data: dict, model_class: Type[T]) -> ValidationResult:
        """用 Pydantic Model 校验字典."""
        try:
            model_class.model_validate(data)
            return ValidationResult(passed=True)
        except ValidationError as e:
            errors = [
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                for err in e.errors()
            ]
            return ValidationResult(
                passed=False,
                errors=errors,
                should_retry=True,
                retry_hint="fix data types and constraints",
            )
