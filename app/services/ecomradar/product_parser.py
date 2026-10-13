"""商品页 HTML 字段抽取器.

支持 4 大国内电商平台:
- 京东 (item.jd.com)
- 淘宝/天猫 (item.taobao.com, detail.tmall.com)
- 拼多多 (mobile.yangkeduo.com)
- 抖音电商 (haohuo.jinritemai.com)

设计要点:
- 不依赖外部 HTML 解析库(避免引入 bs4/lxml 依赖)
- 使用纯正则抽取,实现轻量、可移植
- 各平台 selector 集中管理,便于适配变更
"""
import re
from dataclasses import dataclass, field, asdict


@dataclass
class ProductInfo:
    """商品页结构化信息."""
    title: str = ""
    price: float | None = None
    skus: list[str] = field(default_factory=list)
    sales: str | None = None
    shop_name: str = ""
    description: str = ""
    platform: str = "unknown"
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def is_valid(self) -> bool:
        """商品信息是否足以构成有效记录."""
        return bool(self.title) and self.price is not None


def _strip_html(html: str) -> str:
    """快速去除 HTML 标签,保留文本."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_platform(url: str) -> str:
    """根据 URL 识别电商平台.

    Returns:
        平台标识: jd / tmall / taobao / pdd / douyin / unknown
    """
    url_lower = url.lower()
    if "jd.com" in url_lower:
        return "jd"
    if "tmall.com" in url_lower:
        return "tmall"
    if "taobao.com" in url_lower:
        return "taobao"
    if "yangkeduo.com" in url_lower or "pinduoduo.com" in url_lower:
        return "pdd"
    if "jinritemai.com" in url_lower or "douyin.com" in url_lower:
        return "douyin"
    return "unknown"


def _first_match(pattern: str, html: str, group: int = 1) -> str:
    """正则匹配第一个捕获组,失败返回空串."""
    m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
    if m is None:
        return ""
    return m.group(group).strip()


def _clean_text(text: str) -> str:
    """清理文本:去除空白与图标字符."""
    text = re.sub(r"<img[^>]*alt=[\"']?([^\"'>]*)[\"']?[^>]*/?>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_title(html: str, platform: str) -> str:
    """抽取商品标题."""
    if platform == "jd":
        m = re.search(r'<div[^>]*class=["\']?sku-name["\']?[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
        if m:
            return _clean_text(m.group(1))
    if platform in ("tmall", "taobao"):
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL | re.IGNORECASE)
        if m:
            return _clean_text(m.group(1))
    if platform == "pdd":
        m = re.search(r'class=["\']?goods-title["\']?[^>]*>(.*?)</', html, re.DOTALL | re.IGNORECASE)
        if m:
            return _clean_text(m.group(1))
    if platform == "douyin":
        m = re.search(r'class=["\']?title["\']?[^>]*>(.*?)</', html, re.DOTALL | re.IGNORECASE)
        if m:
            return _clean_text(m.group(1))
    m = re.search(r"<title>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    return _clean_text(m.group(1)) if m else ""


def extract_price(html: str, platform: str) -> float | None:
    """抽取价格(数字部分)."""
    if platform == "jd":
        m = re.search(r'class=["\']?p-price["\']?[^>]*>\s*([\d,]+\.?\d*)\s*<', html, re.DOTALL | re.IGNORECASE)
        if m:
            return _parse_price(m.group(1))
        m = re.search(r"￥\s*([\d,]+\.?\d*)", html)
        if m:
            return _parse_price(m.group(1))
    if platform in ("tmall", "taobao"):
        m = re.search(r'class=["\']?tm-price-num["\']?[^>]*>(.*?)</', html, re.DOTALL | re.IGNORECASE)
        if m:
            return _parse_price(m.group(1))
    if platform == "pdd":
        m = re.search(r'class=["\']?goods-price["\']?[^>]*>(.*?)</', html, re.DOTALL | re.IGNORECASE)
        if m:
            return _parse_price(m.group(1))
    m = re.search(r"[¥￥]\s*([\d,]+\.?\d*)", html)
    if m:
        return _parse_price(m.group(1))
    return None


def _parse_price(text: str) -> float | None:
    """从文本中解析价格数字."""
    cleaned = re.sub(r"[^\d.]", "", text)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_sku(html: str, platform: str) -> list[str]:
    """抽取 SKU 列表(规格/颜色/尺码等)."""
    skus: list[str] = []
    if platform == "jd":
        items = re.findall(r'<div[^>]*class=["\']?item["\']?[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
        skus = [_clean_text(s) for s in items if _clean_text(s)]
    elif platform in ("tmall", "taobao"):
        items = re.findall(r"<li[^>]*>(.*?)</li>", html, re.DOTALL | re.IGNORECASE)
        skus = [_clean_text(s) for s in items if "颜色" in s or "尺码" in s or "规格" in s]
        if not skus:
            skus = [_clean_text(s) for s in items if _clean_text(s)][:5]
    elif platform == "pdd":
        items = re.findall(r'<span[^>]*>(.*?)</span>', html, re.DOTALL | re.IGNORECASE)
        skus = [_clean_text(s) for s in items if _clean_text(s) and len(_clean_text(s)) < 30][:5]
    return [s for s in skus if s]


def extract_sales(html: str, platform: str) -> str | None:
    """抽取销量字符串(如 '5万+' / '8万+人付款')."""
    if platform == "jd":
        m = re.search(r'class=["\']?count["\']?[^>]*>(.*?)</span>', html, re.DOTALL | re.IGNORECASE)
        if m:
            return _clean_text(m.group(1))
    if platform in ("tmall", "taobao"):
        m = re.search(r'class=["\']?tm-count["\']?[^>]*>(.*?)</span>', html, re.DOTALL | re.IGNORECASE)
        if m:
            return _clean_text(m.group(1))
    if platform == "pdd":
        m = re.search(r'class=["\']?sales-num["\']?[^>]*>(.*?)</span>', html, re.DOTALL | re.IGNORECASE)
        if m:
            return _clean_text(m.group(1))
    m = re.search(r"([\d.]+万\+?)(?:人付款|人评价|销量)?", html)
    if m:
        return m.group(1)
    return None


def extract_shop_name(html: str, platform: str) -> str:
    """抽取店铺名."""
    if platform == "jd":
        m = re.search(r'class=["\']?shop-name["\']?[^>]*>(.*?)</a>', html, re.DOTALL | re.IGNORECASE)
        if m:
            return _clean_text(m.group(1))
    if platform in ("tmall", "taobao"):
        m = re.search(r'class=["\']?slogo-shopname["\']?[^>]*>(.*?)</a>', html, re.DOTALL | re.IGNORECASE)
        if m:
            return _clean_text(m.group(1))
    if platform == "pdd":
        m = re.search(r'class=["\']?shop-name["\']?[^>]*>(.*?)</', html, re.DOTALL | re.IGNORECASE)
        if m:
            return _clean_text(m.group(1))
    m = re.search(r'<a[^>]*>([^<]*旗舰店[^<]*)</a>', html)
    if m:
        return _clean_text(m.group(1))
    return ""


def extract_description(html: str, platform: str) -> str:
    """抽取商品描述(简要)."""
    return _strip_html(html)[:500]


def parse_product_page(html: str, url: str) -> ProductInfo:
    """一键解析商品页.

    Args:
        html: 商品页 HTML 内容
        url: 商品页 URL(用于平台识别)

    Returns:
        ProductInfo 结构化对象
    """
    platform = detect_platform(url)
    return ProductInfo(
        title=extract_title(html, platform),
        price=extract_price(html, platform),
        skus=extract_sku(html, platform),
        sales=extract_sales(html, platform),
        shop_name=extract_shop_name(html, platform),
        description=extract_description(html, platform),
        platform=platform,
        url=url,
    )
