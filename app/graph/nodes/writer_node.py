"""Writer Node - 竞品周报生成.

行为:
1. 从 scraped_content 提取竞品信息(brand, price, sku 等)
2. 构造 competitor_matrix 列表
3. 提取价格历史(若有 price_history 字段)
4. 调用 LLM 生成 Markdown 报告
5. 重试时使用不同 prompt 引导改进
"""
import re

from app.graph.state import GraphState
from app.core.logging import get_logger
from app.services.ecomradar.product_parser import parse_product_page, ProductInfo
from app.services.llm import generate_competitor_report

logger = get_logger(__name__)


_BRAND_PATTERNS = [
    (r"小米", "小米"),
    (r"小度", "小度"),
    (r"天猫精灵", "天猫精灵"),
    (r"HomePod", "Apple HomePod"),
    (r"完美日记", "完美日记"),
    (r"花西子", "花西子"),
    (r"珂拉琪", "珂拉琪"),
    (r"3CE", "3CE"),
    (r"YSL", "YSL"),
    (r"拼多多", "拼多多"),
]


def _extract_brand(title: str) -> str:
    """从商品标题中识别品牌."""
    if not title:
        return "未知品牌"
    for pattern, brand in _BRAND_PATTERNS:
        if re.search(pattern, title):
            return brand
    return title[:8].strip() or "未知品牌"


def _build_competitor_matrix(scraped: dict[str, str]) -> list[dict]:
    """从抓取内容构建竞品矩阵."""
    matrix: list[dict] = []
    for url, content in scraped.items():
        if not content:
            continue
        try:
            html_match = re.search(r"<html.*?</html>", content, re.DOTALL | re.IGNORECASE)
            if html_match:
                info = parse_product_page(html_match.group(0), url)
            else:
                info = ProductInfo(
                    title=content.split("\n", 1)[0].lstrip("# ").strip()[:80],
                    platform=info_platform_from_url(url),
                    url=url,
                )
            brand = _extract_brand(info.title)
            matrix.append({
                "brand": brand,
                "platform": info.platform,
                "price": info.price or 0.0,
                "sales": info.sales or "",
                "dsr": None,
                "url": url,
                "title": info.title,
            })
        except Exception as e:
            logger.warning(
                "skipping entry in competitor matrix",
                extra={"node": "writer", "url": url, "error": str(e)},
            )
    return matrix


def info_platform_from_url(url: str) -> str:
    """从 URL 推断平台."""
    url_lower = url.lower()
    if "jd.com" in url_lower:
        return "jd"
    if "tmall.com" in url_lower or "taobao.com" in url_lower:
        return "tmall"
    if "yangkeduo.com" in url_lower:
        return "pdd"
    if "jinritemai.com" in url_lower:
        return "douyin"
    return "unknown"


def _build_scraped_text(scraped: dict[str, str], matrix: list[dict]) -> str:
    """构造给 LLM 的输入文本."""
    if matrix:
        lines = ["# 抓取的竞品数据\n"]
        for i, entry in enumerate(matrix, 1):
            lines.append(
                f"{i}. **{entry['brand']}** ({entry['platform']})\n"
                f"   - 商品: {entry['title']}\n"
                f"   - 价格: ¥{entry['price']:.0f}\n"
                f"   - 销量: {entry['sales'] or '未知'}\n"
            )
        return "\n".join(lines)
    parts = []
    for url, content in scraped.items():
        if content:
            parts.append(f"URL: {url}\n{content[:500]}")
    return "\n\n".join(parts) if parts else "无抓取数据"


def _infer_category(matrix: list[dict], state: GraphState) -> str:
    """推断报告品类."""
    if state.get("report_category"):
        return state["report_category"]
    if not matrix:
        return "未指定品类"
    first_title = matrix[0].get("title", "")
    keywords = {
        "智能音箱": "智能音箱",
        "口红": "美妆口红",
        "手机壳": "手机壳",
        "蓝牙音箱": "蓝牙音箱",
        "钢化膜": "钢化膜",
        "充电线": "充电线",
    }
    for kw, cat in keywords.items():
        if kw in first_title:
            return cat
    return "未指定品类"


def _infer_period(state: GraphState) -> str:
    """推断报告周期."""
    if state.get("report_period"):
        return state["report_period"]
    from datetime import datetime
    week = datetime.now().isocalendar()
    return f"{week.year}-W{week.week:02d}"


async def writer_node(state: GraphState) -> GraphState:
    """Writer Node v2 - 竞品周报.

    输入: scraped_content (dict[url, html_or_markdown])
    输出: report (Markdown 报告), competitor_matrix (list[dict])
    """
    retry_count = state.get("retry_count", 0)
    scraped = state.get("scraped_content", {})
    context = state.get("context_docs", [])

    if not scraped:
        return {
            "report": "",
            "retry_count": retry_count + 1,
            "is_degraded": True,
            "error_messages": state.get("error_messages", []) + ["Writer: no scraped content"],
        }

    matrix = _build_competitor_matrix(scraped)
    category = _infer_category(matrix, state)
    period = _infer_period(state)
    scraped_text = _build_scraped_text(scraped, matrix)
    context_str = "\n\n".join(context) if context else "无相关行业知识"

    try:
        logger.info(
            "writer started",
            extra={
                "node": "writer",
                "retry_count": retry_count,
                "competitors": len(matrix),
                "category": category,
                "period": period,
            },
        )
        report = await generate_competitor_report(
            scraped_content=scraped_text,
            context=context_str,
            retry_count=retry_count,
            category=category,
            period=period,
        )
        logger.info(
            "writer completed",
            extra={"node": "writer", "report_len": len(report)},
        )
        return {
            "report": report,
            "competitor_matrix": matrix,
            "retry_count": retry_count + 1,
        }
    except Exception as e:
        logger.error(
            "writer failed",
            extra={"node": "writer", "error": str(e)},
        )
        return {
            "report": "",
            "competitor_matrix": matrix,
            "retry_count": retry_count + 1,
            "is_degraded": True,
            "error_messages": state.get("error_messages", []) + [f"Writer error: {str(e)}"],
        }
