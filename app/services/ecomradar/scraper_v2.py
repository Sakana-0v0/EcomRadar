"""Scraper 升级版 - 集成 Rate Limiter / Robots / Fallback / Mock.

核心能力:
1. UA 池轮换(降低被识别概率)
2. robots.txt 合规检查(拒绝抓取禁止 URL)
3. 域名级令牌桶限流(避免触发平台频率限制)
4. 三级降级:direct → jina reader → mock
5. 返回结构化 {url: html} dict(向下兼容 scraper.py)

设计目标:
- 与原 scraper.scrape_urls 行为兼容(返回 dict[str, str])
- 失败时优雅降级,流程不中断
- 易于 mock 测试(可注入 _direct_fetch / _jina_fetch)
"""
import asyncio
import random
from typing import Optional

import httpx

from app.core.config import settings
from app.services.ecomradar.fallback_strategy import fetch_with_fallback
from app.services.ecomradar.mock_data import get_mock_product
from app.services.ecomradar.product_parser import ProductInfo
from app.services.ecomradar.rate_limiter import DomainRateLimiter
from app.services.ecomradar.robots_checker import RobotsChecker


DEFAULT_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

_GLOBAL_RATE_LIMITER: Optional[DomainRateLimiter] = None
_GLOBAL_ROBOTS_CHECKER: Optional[RobotsChecker] = None


def _get_rate_limiter() -> DomainRateLimiter:
    global _GLOBAL_RATE_LIMITER
    if _GLOBAL_RATE_LIMITER is None:
        _GLOBAL_RATE_LIMITER = DomainRateLimiter(
            rate=settings.scraper_rate_limit,
            capacity=max(3, int(settings.scraper_rate_limit * 3)),
        )
    return _GLOBAL_RATE_LIMITER


def _get_robots_checker() -> RobotsChecker:
    global _GLOBAL_ROBOTS_CHECKER
    if _GLOBAL_ROBOTS_CHECKER is None:
        _GLOBAL_ROBOTS_CHECKER = RobotsChecker(
            user_agent="EcomRadar",
            cache_ttl=60.0,
        )
    return _GLOBAL_ROBOTS_CHECKER


def _pick_user_agent() -> str:
    return random.choice(DEFAULT_USER_AGENTS)


def _build_headers(url: str) -> dict[str, str]:
    """构造请求头,包含 UA / Referer / Accept."""
    ua = _pick_user_agent()
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if "jd.com" in url:
        headers["Referer"] = "https://www.jd.com/"
    elif "tmall.com" in url or "taobao.com" in url:
        headers["Referer"] = "https://www.taobao.com/"
    elif "yangkeduo.com" in url:
        headers["Referer"] = "https://mobile.yangkeduo.com/"
    elif "jinritemai.com" in url:
        headers["Referer"] = "https://www.jinritemai.com/"
    return headers


async def _direct_fetch(url: str, timeout: float = 5.0) -> str:
    """直接抓取(带限流 + 浏览器 Headers).

    Args:
        url: 目标 URL
        timeout: 单次超时(秒)

    Returns:
        HTML 文本

    Raises:
        httpx.HTTPError / asyncio.TimeoutError
    """
    rate_limiter = _get_rate_limiter()
    await rate_limiter.acquire(url)

    headers = _build_headers(url)
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def _jina_fetch(url: str, timeout: float = 8.0) -> str:
    """通过 r.jina.ai 第三方 reader 抓取(降级方案 1).

    jina 返回 Markdown 格式,适合后续解析。
    """
    jina_url = f"{settings.jina_reader_url.rstrip('/')}/{url}"
    rate_limiter = _get_rate_limiter()
    await rate_limiter.acquire(jina_url)

    headers = {
        "User-Agent": _pick_user_agent(),
        "Accept": "text/plain",
    }
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        response = await client.get(jina_url)
        response.raise_for_status()
        return response.text


async def _mock_fetch(url: str) -> str:
    """返回 mock 数据(降级方案 2).

    将 ProductInfo 序列化为 HTML 文本,保证下游 parser 可正常解析。
    """
    product = get_mock_product(url)
    return _product_to_html(product)


def _product_to_html(product: ProductInfo) -> str:
    """将 ProductInfo 序列化为 HTML(模拟真实商品页结构).

    兼容所有 4 平台的 parser 模式 (jd / tmall / pdd / douyin).
    """
    sku_items = "".join(
        f'<div class="item">{s}</div>' for s in product.skus
    )
    sku_props = "".join(f"<li>规格:{s}</li>" for s in product.skus)
    price_str = f"{product.price:.2f}" if product.price is not None else "0.00"
    sales_str = product.sales or "1万+"
    title = product.title or ""
    shop = product.shop_name or ""
    desc = product.description or ""

    return f"""
<html>
<body>
  <h1>{title}</h1>
  <div class="goods-title">{title}</div>
  <div class="title">{title}</div>
  <div class="sku-name">{title}</div>

  <div class="p-price">{price_str}</div>
  <span class="tm-price-num">{price_str}</span>
  <div class="goods-price">¥{price_str}</div>

  <div class="sku-list">{sku_items}</div>
  <ul class="tm-sale-prop">{sku_props}</ul>
  <div class="sku-row">{sku_items}</div>

  <span class="count">{sales_str}</span>评价
  <span class="tm-count">{sales_str}人付款</span>
  <span class="sales-num">已拼{sales_str}件</span>

  <div class="shop-name">
    <a>{shop}</a>
  </div>
  <a class="slogo-shopname">{shop}</a>

  <div class="description">{desc}</div>
</body>
</html>
"""


async def scrape_urls_v2(
    urls: list[str],
    robots_checker: Optional[RobotsChecker] = None,
) -> dict[str, str]:
    """Scraper v2 主入口 - 多 URL 并发抓取,带三级降级.

    Args:
        urls: 目标 URL 列表
        robots_checker: 可选 robots 检查器. 显式传入时才生效.
                       默认 None = 不检查(避免网络异常时全局阻断)

    Returns:
        {url: html_content} 字典,失败的 URL 对应空字符串
    """
    use_robots = robots_checker is not None

    async def fetch_one(url: str) -> tuple[str, str]:
        if use_robots:
            try:
                allowed = await robots_checker.is_allowed(url)
                if not allowed:
                    return url, ""
            except Exception:
                pass

        result = await fetch_with_fallback(
            url=url,
            direct_fetch=_direct_fetch,
            jina_fetch=_jina_fetch,
            mock_fetch=_mock_fetch,
        )
        return url, result.content

    tasks = [fetch_one(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: dict[str, str] = {}
    for url, content in results:
        if isinstance(content, Exception):
            out[url] = ""
        else:
            out[url] = content
    return out


def reset_globals() -> None:
    """重置全局单例(用于测试)."""
    global _GLOBAL_RATE_LIMITER, _GLOBAL_ROBOTS_CHECKER
    _GLOBAL_RATE_LIMITER = None
    _GLOBAL_ROBOTS_CHECKER = None
