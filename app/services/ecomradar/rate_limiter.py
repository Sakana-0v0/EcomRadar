"""令牌桶限流器.

Token Bucket Algorithm:
- 桶以固定 rate 速率注入 token
- 桶容量上限为 capacity
- 每次 acquire 消耗 1 个 token,桶空时阻塞等待
- 多域名通过 DomainRateLimiter 隔离,每域名独立桶

用途:Scraper 抓取时严格遵守 ≤ 1 req/s,避免触发平台频率限制.
"""
import asyncio
import time
from urllib.parse import urlparse


class TokenBucketRateLimiter:
    """单桶令牌桶限流器."""

    def __init__(self, rate: float, capacity: int):
        """初始化.

        Args:
            rate: 令牌注入速率 (tokens per second)
            capacity: 桶容量上限
        """
        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """根据时间流逝补充 token."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    def available_tokens(self) -> float:
        """当前桶内可用 token 数 (近似)."""
        self._refill()
        return self._tokens

    async def acquire(self, timeout: float | None = None) -> bool:
        """获取 1 个 token. 桶空时阻塞,直至注入新 token.

        Args:
            timeout: 最大等待时间 (秒),None 表示无限等待

        Returns:
            True 表示获取成功,False 表示超时
        """
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= 1:
                    self._tokens -= 1
                    return True
                wait_time = (1 - self._tokens) / self.rate
                if timeout is not None and wait_time > timeout:
                    return False
                asyncio.sleep_func = asyncio.sleep
                await asyncio.sleep(wait_time)


class DomainRateLimiter:
    """按域名隔离的多桶限流器.

    每个域名维护独立的 TokenBucketRateLimiter,
    保证单域名不超过 rate,跨域名独立计数.
    """

    def __init__(self, rate: float, capacity: int):
        """初始化.

        Args:
            rate: 单域名令牌速率 (tokens per second)
            capacity: 单域名桶容量
        """
        self.rate = rate
        self.capacity = capacity
        self._buckets: dict[str, TokenBucketRateLimiter] = {}
        self._lock = asyncio.Lock()

    def _extract_domain(self, url: str) -> str | None:
        """从 URL 抽取域名.

        Returns:
            域名字符串,如 'item.jd.com';非法 URL 返回 None
        """
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return None
            return parsed.netloc
        except Exception:
            return None

    def _get_or_create_bucket(self, domain: str) -> TokenBucketRateLimiter:
        if domain not in self._buckets:
            self._buckets[domain] = TokenBucketRateLimiter(
                rate=self.rate, capacity=self.capacity
            )
        return self._buckets[domain]

    async def acquire(self, url: str, timeout: float | None = None) -> bool:
        """根据 URL 域名获取 token.

        Args:
            url: 目标 URL
            timeout: 最大等待时间

        Returns:
            True 成功,False URL 非法或超时
        """
        domain = self._extract_domain(url)
        if domain is None:
            return False
        async with self._lock:
            bucket = self._get_or_create_bucket(domain)
        return await bucket.acquire(timeout=timeout)

    def bucket_for(self, url: str) -> TokenBucketRateLimiter | None:
        """获取 URL 对应的桶 (用于测试 / 监控)."""
        domain = self._extract_domain(url)
        if domain is None:
            return None
        return self._buckets.get(domain)

    def active_domains(self) -> list[str]:
        """当前已创建的域名列表."""
        return list(self._buckets.keys())
