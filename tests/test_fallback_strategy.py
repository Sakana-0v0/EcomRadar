"""Fallback Strategy + Mock Data 单元测试."""
import pytest
from unittest.mock import AsyncMock

from app.services.ecomradar.fallback_strategy import (
    FallbackResult,
    fetch_with_fallback,
    FALLBACK_LEVELS,
)
from app.services.ecomradar.mock_data import get_mock_product, MOCK_PRODUCTS


class TestMockData:
    def test_get_mock_product_by_url_returns_product(self):
        url = "https://item.jd.com/100012345678.html"
        product = get_mock_product(url)
        assert product is not None
        assert product.platform == "jd"
        assert product.title
        assert product.price is not None

    def test_get_mock_product_unknown_url_returns_default(self):
        product = get_mock_product("https://example.com/unknown")
        assert product is not None
        assert product.platform == "mock"

    def test_mock_products_have_required_fields(self):
        for product in MOCK_PRODUCTS:
            assert product.title
            assert product.price is not None and product.price > 0
            assert product.platform
            assert product.url


class TestFallbackStrategy:
    @pytest.mark.asyncio
    async def test_direct_fetch_succeeds_skips_fallback(self):
        """直接抓取成功时,不走 jina 也不走 mock."""
        direct = AsyncMock(return_value="<html>raw page</html>")
        jina = AsyncMock(return_value="<html>via jina</html>")
        mock = AsyncMock(return_value="<html>via mock</html>")

        result = await fetch_with_fallback(
            url="https://item.jd.com/123.html",
            direct_fetch=direct,
            jina_fetch=jina,
            mock_fetch=mock,
        )

        assert result.content == "<html>raw page</html>"
        assert result.level == "direct"
        assert direct.call_count == 1
        assert jina.call_count == 0
        assert mock.call_count == 0

    @pytest.mark.asyncio
    async def test_falls_back_to_jina_on_direct_failure(self):
        """直接抓取失败 → jina 兜底."""
        direct = AsyncMock(side_effect=Exception("403"))
        jina = AsyncMock(return_value="<html>via jina</html>")
        mock = AsyncMock(return_value="<html>via mock</html>")

        result = await fetch_with_fallback(
            url="https://item.jd.com/123.html",
            direct_fetch=direct,
            jina_fetch=jina,
            mock_fetch=mock,
        )

        assert result.content == "<html>via jina</html>"
        assert result.level == "jina"
        assert direct.call_count == 1
        assert jina.call_count == 1
        assert mock.call_count == 0

    @pytest.mark.asyncio
    async def test_falls_back_to_mock_on_both_failure(self):
        """直接 + jina 都失败 → mock."""
        direct = AsyncMock(side_effect=Exception("403"))
        jina = AsyncMock(side_effect=Exception("timeout"))
        mock = AsyncMock(return_value="<html>via mock</html>")

        result = await fetch_with_fallback(
            url="https://item.jd.com/123.html",
            direct_fetch=direct,
            jina_fetch=jina,
            mock_fetch=mock,
        )

        assert result.content == "<html>via mock</html>"
        assert result.level == "mock"
        assert direct.call_count == 1
        assert jina.call_count == 1
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_records_attempt_chain(self):
        """返回结果包含完整的尝试链."""
        direct = AsyncMock(side_effect=Exception("fail"))
        jina = AsyncMock(return_value="<html>ok</html>")
        mock = AsyncMock()

        result = await fetch_with_fallback(
            url="https://item.jd.com/123.html",
            direct_fetch=direct,
            jina_fetch=jina,
            mock_fetch=mock,
        )

        assert "direct" in result.attempts
        assert "jina" in result.attempts
        assert "jina" in result.success_level


class TestFallbackLevels:
    def test_fallback_levels_order(self):
        assert FALLBACK_LEVELS == ["direct", "jina", "mock"]
