from typing import TypedDict


class GraphState(TypedDict, total=False):
    """EcomRadar 状态机共享状态.

    字段分组:
    - 输入: urls, task_id, tenant_id (Phase 6 新增)
    - 抓取层: scraped_content, is_degraded, error_messages
    - 检索层: chunks, context_docs
    - 报告层: report, quality_score, retry_count
    - 竞品业务字段: competitor_matrix, price_history
    - 多租户 (Phase 6): tenant_id
    """
    urls: list[str]
    task_id: str
    tenant_id: str
    scraped_content: dict[str, str]
    chunks: list[str]
    context_docs: list[str]
    report: str
    quality_score: int
    retry_count: int
    is_degraded: bool
    error_messages: list[str]

    competitor_matrix: list[dict]
    price_history: dict[str, list[float]]
    report_period: str
    report_category: str
