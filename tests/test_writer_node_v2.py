"""Writer Node v2 单元测试."""
import pytest
from unittest.mock import AsyncMock, patch

from app.graph.nodes.writer_node import (
    writer_node,
    _extract_brand,
    _build_competitor_matrix,
    _build_scraped_text,
    _infer_category,
)


SAMPLE_SCRAPED = {
    "https://item.jd.com/100012345678.html": """<html><body>
<div class="sku-name">小度智能音箱 1S 旗舰版 白色 蓝牙WiFi</div>
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
<div class="sku-name">小米小爱同学 Play 增强版</div>
<div class="p-price">349.00</div>
</body></html>""",
}


class TestExtractBrand:
    def test_known_brands(self):
        assert _extract_brand("小度智能音箱") == "小度"
        assert _extract_brand("小米小爱同学") == "小米"
        assert _extract_brand("天猫精灵IN糖") == "天猫精灵"
        assert _extract_brand("Apple HomePod") == "Apple HomePod"
        assert _extract_brand("完美日记口红") == "完美日记"
        assert _extract_brand("花西子苗族印象") == "花西子"

    def test_unknown_brand_returns_truncated_title(self):
        brand = _extract_brand("某品牌商品标题非常长测试")
        assert len(brand) <= 8
        assert brand != "未知品牌"

    def test_empty_title(self):
        assert _extract_brand("") == "未知品牌"


class TestBuildCompetitorMatrix:
    def test_builds_matrix_from_scraped(self):
        matrix = _build_competitor_matrix(SAMPLE_SCRAPED)
        assert len(matrix) == 3
        assert matrix[0]["brand"] in ("小度", "天猫精灵", "小米")
        assert all(m["price"] > 0 for m in matrix)

    def test_skips_empty_content(self):
        scraped = {
            "https://item.jd.com/123.html": "",
            "https://item.jd.com/456.html": "<html><body>empty</body></html>",
        }
        matrix = _build_competitor_matrix(scraped)
        assert len(matrix) == 1

    def test_handles_malformed_html_gracefully(self):
        scraped = {
            "https://item.jd.com/123.html": "no html here just text",
        }
        matrix = _build_competitor_matrix(scraped)
        assert len(matrix) == 1
        assert matrix[0]["title"]


class TestBuildScrapedText:
    def test_uses_matrix_when_available(self):
        matrix = [{"brand": "A", "platform": "jd", "price": 100.0, "sales": "1w+", "title": "T"}]
        text = _build_scraped_text({}, matrix)
        assert "**A**" in text
        assert "¥100" in text

    def test_falls_back_to_raw_content(self):
        text = _build_scraped_text({"u": "raw content"}, [])
        assert "raw content" in text

    def test_empty_inputs(self):
        text = _build_scraped_text({}, [])
        assert "无抓取数据" in text


class TestInferCategory:
    def test_infers_from_title(self):
        matrix = [{"title": "智能音箱旗舰版", "platform": "jd", "price": 100}]
        assert _infer_category(matrix, {}) == "智能音箱"

    def test_infers_lipstick(self):
        matrix = [{"title": "丝绒口红", "platform": "tmall", "price": 100}]
        assert _infer_category(matrix, {}) == "美妆口红"

    def test_uses_explicit_state_category(self):
        matrix = [{"title": "智能音箱", "platform": "jd", "price": 100}]
        state = {"report_category": "定制品类"}
        assert _infer_category(matrix, state) == "定制品类"

    def test_empty_matrix(self):
        assert _infer_category([], {}) == "未指定品类"


class TestWriterNode:
    @pytest.mark.asyncio
    async def test_generates_report_with_competitor_matrix(self):
        """writer_node 应当生成 report + competitor_matrix."""
        mock_report = """# 竞品周报 - 智能音箱

## Executive Summary
本周动态

## 竞品矩阵对比

| 品牌 | 平台 | 价格 | 销量 | DSR | 关键动作 |
|------|------|------|------|-----|----------|
| 小度 | jd | 329 | 5w+ | 4.8 | - |

## 价格波动分析

| 品牌 | 旧价 | 新价 | 变化 |
|------|------|------|------|
| 小度 | 329 | 329 | → 0.0% |

## 行动建议

**1. 错位定价** — 音质升级
"""
        with patch(
            "app.graph.nodes.writer_node.generate_competitor_report",
            new=AsyncMock(return_value=mock_report),
        ):
            state = {
                "scraped_content": SAMPLE_SCRAPED,
                "context_docs": [],
                "retry_count": 0,
                "error_messages": [],
            }
            result = await writer_node(state)

        assert "report" in result
        assert "competitor_matrix" in result
        assert len(result["competitor_matrix"]) == 3
        assert result["retry_count"] == 1
        assert "Executive Summary" in result["report"]

    @pytest.mark.asyncio
    async def test_handles_empty_scraped_content(self):
        state = {
            "scraped_content": {},
            "context_docs": [],
            "retry_count": 0,
            "error_messages": [],
        }
        result = await writer_node(state)
        assert result.get("is_degraded") is True
        assert "no scraped content" in " ".join(result.get("error_messages", []))

    @pytest.mark.asyncio
    async def test_increments_retry_count(self):
        mock_report = "# 竞品周报\n\n## Executive Summary\ntest"
        with patch(
            "app.graph.nodes.writer_node.generate_competitor_report",
            new=AsyncMock(return_value=mock_report),
        ):
            state = {
                "scraped_content": SAMPLE_SCRAPED,
                "context_docs": [],
                "retry_count": 0,
                "error_messages": [],
            }
            result = await writer_node(state)
            assert result["retry_count"] == 1
