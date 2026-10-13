"""竞品报告 Pydantic Schema.

定义 EcomRadar 竞品报告的数据结构,支持 4 段式输出:
1. Executive Summary - 3~5 句核心洞察
2. 竞品矩阵对比 - Markdown 表格
3. 价格波动分析 - 涨/降/促销
4. 行动建议 - 3~5 条可执行项

设计原则:
- Pydantic v2 严格校验
- to_markdown() 直接生成符合 SSE 推流的文本
- 字段可选,支持最小化报告
"""
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CompetitorEntry(BaseModel):
    """单个竞品快照."""
    brand: str = Field(..., min_length=1, description="品牌名")
    platform: str = Field(..., min_length=1, description="平台标识")
    price: float = Field(..., gt=0, description="价格(CNY)")
    sales: str = Field(default="", description="销量字符串")
    dsr: Optional[float] = Field(default=None, ge=0, le=5, description="DSR 评分 0~5")
    key_action: str = Field(default="", description="关键动作/策略")

    model_config = {"frozen": False}


class PriceChange(BaseModel):
    """价格变动记录."""
    brand: str = Field(..., min_length=1)
    old_price: float = Field(..., gt=0)
    new_price: float = Field(..., gt=0)
    change_pct: float = Field(..., description="变化百分比,可正可负")


class ActionItem(BaseModel):
    """行动建议项."""
    priority: int = Field(..., ge=1, le=5, description="优先级 1~5")
    title: str = Field(..., min_length=1, description="建议标题")
    description: str = Field(..., min_length=1, description="建议详情")

    @field_validator("title", "description")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v


class ReportSection(BaseModel):
    """报告分节."""
    heading: str
    content: str


class CompetitorReport(BaseModel):
    """竞品报告主体."""
    category: str = Field(..., min_length=1, description="品类")
    period: str = Field(..., min_length=1, description="周期,如 2026-W42")
    executive_summary: str = Field(default="", description="3~5 句核心洞察")
    competitor_matrix: list[CompetitorEntry] = Field(default_factory=list)
    price_changes: list[PriceChange] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)

    def to_markdown(self) -> str:
        """生成完整的 Markdown 报告."""
        parts: list[str] = []

        parts.append(f"# 竞品周报 - {self.category}")
        parts.append(f"\n**周期**: {self.period}\n")

        if self.executive_summary:
            parts.append("## Executive Summary\n")
            parts.append(self.executive_summary)
            parts.append("")

        if self.competitor_matrix:
            parts.append("## 竞品矩阵对比\n")
            parts.append("| 品牌 | 平台 | 价格 | 销量 | DSR | 关键动作 |")
            parts.append("|------|------|------|------|-----|----------|")
            for entry in self.competitor_matrix:
                dsr_str = f"{entry.dsr}" if entry.dsr is not None else "-"
                parts.append(
                    f"| {entry.brand} | {entry.platform} | ¥{entry.price:.0f} | "
                    f"{entry.sales or '-'} | {dsr_str} | {entry.key_action or '-'} |"
                )
            parts.append("")

        if self.price_changes:
            parts.append("## 价格波动分析\n")
            parts.append("| 品牌 | 旧价 | 新价 | 变化 |")
            parts.append("|------|------|------|------|")
            for change in self.price_changes:
                arrow = "↑" if change.change_pct > 0 else "↓" if change.change_pct < 0 else "→"
                parts.append(
                    f"| {change.brand} | ¥{change.old_price:.0f} | "
                    f"¥{change.new_price:.0f} | {arrow} {change.change_pct:+.1f}% |"
                )
            parts.append("")

        if self.action_items:
            parts.append("## 行动建议\n")
            sorted_items = sorted(self.action_items, key=lambda x: x.priority)
            for item in sorted_items:
                parts.append(
                    f"**{item.priority}. {item.title}** — {item.description}"
                )
            parts.append("")

        return "\n".join(parts)
