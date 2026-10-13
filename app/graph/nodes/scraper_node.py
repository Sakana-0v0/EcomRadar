from app.graph.state import GraphState
from app.core.logging import get_logger
from app.services.ecomradar.scraper_v2 import scrape_urls_v2
from app.services.ecomradar.product_parser import parse_product_page

logger = get_logger(__name__)


async def scraper_node(state: GraphState) -> GraphState:
    """Scraper Node v2 - 集成 Rate Limiter / Robots / 三级降级.

    行为:
    1. 调用 scrape_urls_v2 抓取所有 URL
    2. 对每个 URL 的 HTML 调用 parse_product_page 抽取结构化字段
    3. 将结构化字段转为 Markdown 文本写入 scraped_content
    4. 抓取失败/降级到 mock 时,日志明确标注
    """
    urls = state.get("urls", [])
    error_messages: list[str] = []

    if not urls:
        return {
            "scraped_content": {},
            "error_messages": state.get("error_messages", []) + ["No URLs provided"],
        }

    try:
        scraped = await scrape_urls_v2(urls)
    except Exception as e:
        logger.error("scraper v2 failed", extra={"node": "scraper", "error": str(e)})
        return {
            "scraped_content": {},
            "is_degraded": True,
            "error_messages": state.get("error_messages", []) + [f"Scraper error: {str(e)}"],
        }

    enriched: dict[str, str] = {}
    for url, html in scraped.items():
        if not html:
            error_messages.append(f"Empty content: {url}")
            continue
        try:
            info = parse_product_page(html, url)
            enriched[url] = info.to_dict() and _product_to_markdown(info)
        except Exception as e:
            error_messages.append(f"Parse error: {url}: {e}")
            enriched[url] = html

    return {
        "scraped_content": enriched,
        "is_degraded": bool(error_messages),
        "error_messages": state.get("error_messages", []) + error_messages,
    }


def _product_to_markdown(info) -> str:
    """将 ProductInfo 序列化为 Markdown 文本,便于后续 Writer 处理."""
    parts = [
        f"# {info.title}",
        f"\n**平台**: {info.platform}",
        f"**店铺**: {info.shop_name}",
        f"**价格**: ¥{info.price:.2f}" if info.price is not None else "**价格**: 未知",
    ]
    if info.sales:
        parts.append(f"**销量**: {info.sales}")
    if info.skus:
        parts.append(f"\n**SKU 选项**: {', '.join(info.skus)}")
    if info.description:
        parts.append(f"\n## 商品描述\n\n{info.description[:300]}")
    return "\n".join(parts)