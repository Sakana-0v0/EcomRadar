"""Product Parser 单元测试 (HTML 字段抽取)."""
import pytest

from app.services.ecomradar.product_parser import (
    ProductInfo,
    parse_product_page,
    extract_title,
    extract_price,
    extract_sku,
    extract_sales,
    extract_shop_name,
    extract_description,
    detect_platform,
)


SAMPLE_JD_HTML = """
<html>
<head><title>京东商品页</title></head>
<body>
  <div class="sku-name">
    <img alt="icon"/>
    小度智能音箱 1S 旗舰版 白色 蓝牙WiFi 语音控制
  </div>
  <div class="p-price">
    <span class="price">¥</span>
    <span class="p-price">329.00</span>
  </div>
  <div class="sku-list">
    <div class="item selected">白色</div>
    <div class="item">黑色</div>
  </div>
  <div class="summary">
    <span class="count">5万+</span>评价
  </div>
  <div class="shop-name">
    <a>小度旗舰店</a>
  </div>
</body>
</html>
"""

SAMPLE_TMALL_HTML = """
<html>
<body>
  <h1 data-spm="title">天猫精灵IN糖 智能音箱 蓝牙音响 语音助手</h1>
  <div class="tm-price">
    <span class="tm-yen">¥</span>
    <span class="tm-price-num">263.00</span>
  </div>
  <ul class="tm-sale-prop">
    <li>颜色:白色</li>
    <li>颜色:黑色</li>
  </ul>
  <span class="tm-count">8万+人付款</span>
  <a class="slogo-shopname">天猫精灵旗舰店</a>
</body>
</html>
"""

SAMPLE_PDD_HTML = """
<html>
<body>
  <h1 class="goods-title">拼多多爆款手机壳 透明硅胶 iPhone 15 适用</h1>
  <div class="goods-price">¥9.9</div>
  <div class="sku-row">
    <span>iPhone 15</span><span>iPhone 14</span>
  </div>
  <span class="sales-num">已拼10万件</span>
  <span class="shop-name">数码优品</span>
</body>
</html>
"""


class TestProductInfo:
    def test_to_dict_serializes_all_fields(self):
        info = ProductInfo(
            title="test",
            price=99.0,
            skus=["A", "B"],
            sales="1万+",
            shop_name="旗舰店",
            platform="jd",
        )
        d = info.to_dict()
        assert d["title"] == "test"
        assert d["price"] == 99.0
        assert d["platform"] == "jd"

    def test_default_values(self):
        info = ProductInfo()
        assert info.title == ""
        assert info.price is None
        assert info.skus == []
        assert info.platform == "unknown"


class TestExtractTitle:
    def test_jd_sku_name(self):
        assert extract_title(SAMPLE_JD_HTML, "jd") == "小度智能音箱 1S 旗舰版 白色 蓝牙WiFi 语音控制"

    def test_tmall_h1(self):
        assert extract_title(SAMPLE_TMALL_HTML, "tmall") == "天猫精灵IN糖 智能音箱 蓝牙音响 语音助手"

    def test_pdd_goods_title(self):
        assert extract_title(SAMPLE_PDD_HTML, "pdd") == "拼多多爆款手机壳 透明硅胶 iPhone 15 适用"

    def test_empty_html(self):
        assert extract_title("", "jd") == ""

    def test_unknown_platform_falls_back_to_title_tag(self):
        html = "<html><body><title>商品标题</title></body></html>"
        assert extract_title(html, "unknown") == "商品标题"


class TestExtractPrice:
    def test_jd_price(self):
        assert extract_price(SAMPLE_JD_HTML, "jd") == 329.0

    def test_tmall_price(self):
        assert extract_price(SAMPLE_TMALL_HTML, "tmall") == 263.0

    def test_pdd_price(self):
        assert extract_price(SAMPLE_PDD_HTML, "pdd") == 9.9

    def test_no_price_returns_none(self):
        assert extract_price("<html></html>", "jd") is None

    def test_strips_currency_symbol(self):
        html = '<span class="price">¥1,299.00</span>'
        assert extract_price(html, "jd") == 1299.0


class TestExtractSku:
    def test_jd_sku_list(self):
        skus = extract_sku(SAMPLE_JD_HTML, "jd")
        assert "白色" in skus
        assert "黑色" in skus

    def test_tmall_sale_prop(self):
        skus = extract_sku(SAMPLE_TMALL_HTML, "tmall")
        assert any("白色" in s for s in skus)
        assert any("黑色" in s for s in skus)

    def test_pdd_sku_row(self):
        skus = extract_sku(SAMPLE_PDD_HTML, "pdd")
        assert "iPhone 15" in skus
        assert "iPhone 14" in skus

    def test_no_sku_returns_empty(self):
        assert extract_sku("<html></html>", "jd") == []


class TestExtractSales:
    def test_jd_count(self):
        sales = extract_sales(SAMPLE_JD_HTML, "jd")
        assert sales is not None
        assert "5" in sales

    def test_tmall_count(self):
        sales = extract_sales(SAMPLE_TMALL_HTML, "tmall")
        assert sales is not None
        assert "8" in sales

    def test_pdd_count(self):
        sales = extract_sales(SAMPLE_PDD_HTML, "pdd")
        assert sales is not None
        assert "10" in sales


class TestExtractShopName:
    def test_jd_shop(self):
        assert extract_shop_name(SAMPLE_JD_HTML, "jd") == "小度旗舰店"

    def test_tmall_shop(self):
        assert extract_shop_name(SAMPLE_TMALL_HTML, "tmall") == "天猫精灵旗舰店"

    def test_pdd_shop(self):
        assert extract_shop_name(SAMPLE_PDD_HTML, "pdd") == "数码优品"


class TestDetectPlatform:
    def test_jd(self):
        assert detect_platform("https://item.jd.com/123.html") == "jd"
        assert detect_platform("https://www.jd.com/product/456") == "jd"

    def test_tmall(self):
        assert detect_platform("https://detail.tmall.com/item.htm?id=1") == "tmall"

    def test_taobao(self):
        assert detect_platform("https://item.taobao.com/item.htm?id=2") == "taobao"

    def test_pdd(self):
        assert detect_platform("https://mobile.yangkeduo.com/goods.html?goods_id=1") == "pdd"

    def test_douyin(self):
        assert detect_platform("https://haohuo.jinritemai.com/1") == "douyin"

    def test_unknown(self):
        assert detect_platform("https://example.com/product/1") == "unknown"


class TestParseProductPage:
    def test_full_parse_jd(self):
        info = parse_product_page(SAMPLE_JD_HTML, "https://item.jd.com/123.html")
        assert info.platform == "jd"
        assert "小度" in info.title
        assert info.price == 329.0
        assert "白色" in info.skus
        assert "小度旗舰店" in info.shop_name

    def test_full_parse_tmall(self):
        info = parse_product_page(SAMPLE_TMALL_HTML, "https://detail.tmall.com/item.htm?id=1")
        assert info.platform == "tmall"
        assert "天猫精灵" in info.title
        assert info.price == 263.0

    def test_full_parse_pdd(self):
        info = parse_product_page(SAMPLE_PDD_HTML, "https://mobile.yangkeduo.com/goods.html?goods_id=1")
        assert info.platform == "pdd"
        assert info.price == 9.9
