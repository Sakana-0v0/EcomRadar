"""Scraper 升级版单元测试."""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.ecomradar.scraper_v2 import (
    scrape_urls_v2,
    DEFAULT_USER_AGENTS,
)


SAMPLE_HTML = """
<html>
<body>
  <div class="sku-name">测试商品标题 红色 256G</div>
  <div class="p-price"><span class="p-price">199.00</span></div>
  <span class="count">1万+</span>评价
</body>
</html>
"""


class TestScrapeUrlsV2:
    @pytest.mark.asyncio
    async def test_returns_dict_of_url_to_html(self):
        """正常抓取返回 {url: html}."""
        with patch(
            "app.services.ecomradar.scraper_v2._direct_fetch",
            new=AsyncMock(return_value=SAMPLE_HTML),
        ):
            results = await scrape_urls_v2(
                urls=["https://item.jd.com/123.html"],
                robots_checker=None,
            )
            assert "https://item.jd.com/123.html" in results
            assert "测试商品标题" in results["https://item.jd.com/123.html"]

    @pytest.mark.asyncio
    async def test_skips_robots_disallowed_urls(self):
        """robots.txt 禁止的 URL 跳过抓取,返回空字符串."""
        mock_robots = AsyncMock()
        mock_robots.is_allowed = AsyncMock(return_value=False)
        with patch(
            "app.services.ecomradar.scraper_v2._direct_fetch",
            new=AsyncMock(),
        ) as direct:
            results = await scrape_urls_v2(
                urls=["https://example.com/admin"],
                robots_checker=mock_robots,
            )
            assert results["https://example.com/admin"] == ""
            assert direct.call_count == 0

    @pytest.mark.asyncio
    async def test_falls_back_to_jina_on_failure(self):
        """直接抓取失败时,jina 兜底."""
        jina_called = []

        async def jina_fetch(url):
            jina_called.append(url)
            return SAMPLE_HTML

        with patch(
            "app.services.ecomradar.scraper_v2._direct_fetch",
            new=AsyncMock(side_effect=Exception("403")),
        ):
            with patch(
                "app.services.ecomradar.scraper_v2._jina_fetch",
                new=AsyncMock(side_effect=jina_fetch),
            ):
                results = await scrape_urls_v2(
                    urls=["https://item.jd.com/123.html"],
                    robots_checker=None,
                )
                assert len(jina_called) == 1
                assert "测试商品标题" in results["https://item.jd.com/123.html"]

    @pytest.mark.asyncio
    async def test_falls_back_to_mock_on_both_failure(self):
        """直接 + jina 都失败时,mock 兜底."""
        with patch(
            "app.services.ecomradar.scraper_v2._direct_fetch",
            new=AsyncMock(side_effect=Exception("err")),
        ):
            with patch(
                "app.services.ecomradar.scraper_v2._jina_fetch",
                new=AsyncMock(side_effect=Exception("err")),
            ):
                results = await scrape_urls_v2(
                    urls=["https://item.jd.com/123.html"],
                    robots_checker=None,
                )
                # mock 数据也有 title
                assert results["https://item.jd.com/123.html"]


class TestUserAgentPool:
    def test_user_agents_have_variety(self):
        """UA 池至少 3 个,降低被识别概率."""
        assert len(DEFAULT_USER_AGENTS) >= 3
        for ua in DEFAULT_USER_AGENTS:
            assert "Mozilla" in ua or "Chrome" in ua or "Safari" in ua

    def test_user_agents_are_distinct(self):
        seen = set()
        for ua in DEFAULT_USER_AGENTS:
            assert ua not in seen
            seen.add(ua)
