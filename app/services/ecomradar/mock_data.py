"""虚构商品数据(用于抓取失败兜底).

设计原则:
- 仅在 Scraper 抓取失败时使用,保证演示不中断
- 字段结构与 ProductInfo 完全一致
- URL 哈希 → 固定 mock 商品,保证多次调用稳定
- 包含 4 平台示例,覆盖 Phase 1 演示场景
"""
import hashlib
from typing import Optional

from app.services.ecomradar.product_parser import ProductInfo


MOCK_PRODUCTS: list[ProductInfo] = [
    ProductInfo(
        title="小度智能音箱 1S 旗舰版 白色 蓝牙WiFi 语音控制",
        price=329.0,
        skus=["白色", "黑色", "红色"],
        sales="5万+",
        shop_name="小度旗舰店",
        description="小度智能音箱 1S 旗舰版,搭载百度 DuerOS,支持蓝牙 WiFi 语音控制...",
        platform="jd",
        url="https://item.jd.com/100012345678.html",
    ),
    ProductInfo(
        title="天猫精灵 IN糖 智能音箱 蓝牙音响 语音助手",
        price=263.0,
        skus=["白色", "黑色"],
        sales="8万+",
        shop_name="天猫精灵旗舰店",
        description="天猫精灵 IN糖,阿里旗下智能音箱,支持语音购物...",
        platform="tmall",
        url="https://detail.tmall.com/item.htm?id=655000012345",
    ),
    ProductInfo(
        title="小米小爱同学 Play 增强版 智能音箱",
        price=349.0,
        skus=["白色"],
        sales="3万+",
        shop_name="小米旗舰店",
        description="小米小爱同学 Play 增强版,支持米家生态联动...",
        platform="jd",
        url="https://item.jd.com/100023456789.html",
    ),
    ProductInfo(
        title="Apple HomePod mini 智能音箱 太空灰",
        price=2299.0,
        skus=["太空灰", "白色", "黄色", "蓝色"],
        sales="5千+",
        shop_name="Apple Store 官方旗舰店",
        description="HomePod mini,Apple 出品,搭载 S5 芯片,支持 Siri 语音控制...",
        platform="tmall",
        url="https://detail.tmall.com/item.htm?id=655023456789",
    ),
    ProductInfo(
        title="拼多多爆款 iPhone 15 透明硅胶手机壳 磁吸 MagSafe",
        price=9.9,
        skus=["iPhone 15", "iPhone 14", "iPhone 13"],
        sales="10万+",
        shop_name="数码优品工厂店",
        description="透明硅胶磁吸手机壳,适配 iPhone 15 系列,支持 MagSafe 充电...",
        platform="pdd",
        url="https://mobile.yangkeduo.com/goods.html?goods_id=123456789",
    ),
    ProductInfo(
        title="抖音电商同款 小型蓝牙音箱 户外便携",
        price=89.0,
        skus=["黑色", "军绿色"],
        sales="2万+",
        shop_name="声立方数码旗舰店",
        description="小型蓝牙音箱,户外便携设计,IPX7 防水...",
        platform="douyin",
        url="https://haohuo.jinritemai.com/views/product/item2?id=987654321",
    ),
]


_DEFAULT_MOCK = ProductInfo(
    title="通用商品 占位数据",
    price=99.0,
    skus=["默认规格"],
    sales="1万+",
    shop_name="示例店铺",
    description="该商品为 mock 数据,实际抓取失败时使用...",
    platform="mock",
    url="",
)


def _match_mock_by_url(url: str) -> Optional[ProductInfo]:
    """根据 URL 域名匹配对应的 mock 商品."""
    url_lower = url.lower()
    for product in MOCK_PRODUCTS:
        if not product.url:
            continue
        product_domain = product.url.lower()
        if "jd.com" in url_lower and "jd.com" in product_domain:
            return product
        if "tmall.com" in url_lower and "tmall.com" in product_domain:
            return product
        if "yangkeduo.com" in url_lower and "yangkeduo.com" in product_domain:
            return product
        if "jinritemai.com" in url_lower and "jinritemai.com" in product_domain:
            return product
    return None


def _match_mock_by_hash(url: str) -> ProductInfo:
    """URL 哈希取模,稳定选择 mock."""
    h = hashlib.md5(url.encode("utf-8")).hexdigest()
    idx = int(h, 16) % len(MOCK_PRODUCTS)
    return MOCK_PRODUCTS[idx]


def get_mock_product(url: str) -> ProductInfo:
    """根据 URL 返回 mock 商品.

    策略:
    1. 按 URL 域名匹配同平台 mock(保留真实字段)
    2. 否则返回通用占位(platform="mock")

    Args:
        url: 原始 URL

    Returns:
        ProductInfo 对象
    """
    matched = _match_mock_by_url(url)
    if matched is not None:
        return matched
    placeholder = ProductInfo(
        title=_DEFAULT_MOCK.title,
        price=_DEFAULT_MOCK.price,
        skus=list(_DEFAULT_MOCK.skus),
        sales=_DEFAULT_MOCK.sales,
        shop_name=_DEFAULT_MOCK.shop_name,
        description=_DEFAULT_MOCK.description,
        platform="mock",
        url=url,
    )
    return placeholder
