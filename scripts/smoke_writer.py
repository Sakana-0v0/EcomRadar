"""Writer Node end-to-end smoke test (uses mock scraped data, no real LLM)."""
import asyncio
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


async def main():
    from app.graph.nodes.writer_node import writer_node
    from app.schemas.ecom_report import CompetitorReport
    from app.services.evaluator import evaluate_competitor_report

    state = {
        "scraped_content": {
            "https://item.jd.com/100012345678.html": """<html><body>
<div class="sku-name">小度智能音箱 1S 旗舰版</div>
<div class="p-price">329.00</div>
<div class="item">白色</div><div class="item">黑色</div>
<span class="count">5万+</span>评价
<div class="shop-name"><a>小度旗舰店</a></div>
</body></html>""",
            "https://detail.tmall.com/item.htm?id=1": """<html><body>
<h1>天猫精灵 IN糖 智能音箱</h1>
<span class="tm-price-num">263.00</span>
<span class="tm-count">8万+人付款</span>
</body></html>""",
            "https://item.jd.com/100023456789.html": """<html><body>
<div class="sku-name">小米小爱同学 Play</div>
<div class="p-price">349.00</div>
</body></html>""",
        },
        "context_docs": [],
        "retry_count": 0,
        "error_messages": [],
    }

    print("=" * 60)
    print("Writer Node Smoke Test (no LLM)")
    print("=" * 60)

    matrix = state.get("scraped_content", {})
    print(f"\nCompetitor matrix built from {len(matrix)} URLs")

    result = await writer_node(state)
    print(f"\nGenerated report length: {len(result.get('report', ''))}")
    print(f"Retry count: {result.get('retry_count')}")
    print(f"Is degraded: {result.get('is_degraded', False)}")
    print(f"Matrix entries: {len(result.get('competitor_matrix', []))}")

    print("\n" + "=" * 60)
    print("Sample mock report (using Schema directly):")
    print("=" * 60)

    from app.schemas.ecom_report import (
        CompetitorEntry, PriceChange, ActionItem,
    )

    report_obj = CompetitorReport(
        category="智能音箱",
        period="2026-W42",
        executive_summary="本周天猫精灵降价 12%, 小度新增户外 SKU, 小爱差评率上升 3pp",
        competitor_matrix=[
            CompetitorEntry(brand="小度", platform="jd", price=329.0, sales="5w+", dsr=4.8, key_action="新增户外 SKU"),
            CompetitorEntry(brand="天猫精灵", platform="tmall", price=263.0, sales="8w+", dsr=4.9, key_action="大促降价"),
            CompetitorEntry(brand="小米", platform="jd", price=349.0, sales="3w+", dsr=4.6, key_action="联名款"),
        ],
        price_changes=[
            PriceChange(brand="天猫精灵", old_price=299.0, new_price=263.0, change_pct=-12.0),
        ],
        action_items=[
            ActionItem(priority=1, title="错位定价", description="在 299-399 价格带做音质升级"),
            ActionItem(priority=2, title="内容种草", description="抖音/小红书蓝牙连接稳定性实测"),
        ],
    )

    md = report_obj.to_markdown()
    print(md)
    print("=" * 60)

    evaluation = evaluate_competitor_report(md)
    print(f"\nEvaluator Score: {evaluation.score}/100 (passed={evaluation.passed})")
    print(f"Dimensions: {evaluation.dimensions}")
    print(f"Missing sections: {evaluation.missing_sections}")


if __name__ == "__main__":
    asyncio.run(main())
