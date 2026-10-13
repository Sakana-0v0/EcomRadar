"""Smoke test: Scraper v2 三级降级链路."""
import asyncio
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


async def main():
    print("=" * 60)
    print("Scraper v2 Offline Demo (mock-only mode)")
    print("=" * 60)

    from app.services.ecomradar.scraper_v2 import _mock_fetch
    from app.services.ecomradar.product_parser import parse_product_page
    from app.services.ecomradar.fallback_strategy import fetch_with_fallback

    test_urls = [
        "https://item.jd.com/100012345678.html",
        "https://detail.tmall.com/item.htm?id=655000012345",
        "https://mobile.yangkeduo.com/goods.html?goods_id=123456789",
        "https://haohuo.jinritemai.com/views/product/item2?id=987654321",
    ]

    for url in test_urls:
        print(f"\n--- URL: {url} ---")
        html = await _mock_fetch(url)
        info = parse_product_page(html, url)
        print(f"  Title:    {info.title}")
        print(f"  Price:    {info.price} CNY")
        print(f"  Shop:     {info.shop_name}")
        print(f"  Platform: {info.platform}")
        print(f"  SKUs:     {info.skus}")

    print("\n" + "=" * 60)
    print("Fallback Chain Test (direct + jina fail, mock succeeds)")
    print("=" * 60)

    async def failing_direct(url):
        raise Exception("403 Forbidden")

    async def failing_jina(url):
        raise Exception("Connection timeout")

    result = await fetch_with_fallback(
        url="https://item.jd.com/test.html",
        direct_fetch=failing_direct,
        jina_fetch=failing_jina,
        mock_fetch=_mock_fetch,
    )
    print(f"  Success level:  {result.success_level}")
    print(f"  Attempted:      {result.attempts}")
    print(f"  Content length: {len(result.content)} bytes")
    print(f"  Errors:         {result.error_messages}")


if __name__ == "__main__":
    asyncio.run(main())
