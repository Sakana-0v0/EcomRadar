"""Robots.txt 合规检查器.

实现:
- 解析 robots.txt 协议 (RFC 9309)
- 缓存抓取结果(默认 60s TTL)
- 404 (无 robots.txt) → 允许
- 网络错误/超时 → 保守拒绝
- 支持最长匹配优先的 Allow/Disallow 解析

设计取舍:
- 404 (无 robots.txt) → 允许抓取,符合 RFC 9309 惯例
- 网络错误 → 保守拒绝,符合"安全优先"原则
- 缓存粒度:按 host 维度缓存,避免重复抓取
"""
import asyncio
import time
from typing import Literal
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx


FetchResult = Literal["NOT_FOUND", "ERROR"] | str


@dataclass
class RobotsRules:
    """单 host 的 robots 规则."""
    disallow: list[str] = field(default_factory=list)
    allow: list[str] = field(default_factory=list)


def parse_robots_txt(text: str) -> dict[str, list[str]]:
    """解析 robots.txt 文本.

    Returns:
        {"disallow": [...], "allow": [...]} 规则字典
    """
    rules: dict[str, list[str]] = {"disallow": [], "allow": []}
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "disallow" and value:
            rules["disallow"].append(value)
        elif key == "allow" and value:
            rules["allow"].append(value)
    return rules


def is_path_allowed(path: str, rules: dict[str, list[str]]) -> bool:
    """判断给定路径是否被允许抓取.

    算法:
    1. 找出所有 disallow 规则中最长的匹配
    2. 找出所有 allow 规则中最长的匹配
    3. 较长者胜出;平局时 allow 胜
    4. 无匹配则默认 allow

    Args:
        path: URL 路径部分,如 '/admin/users'
        rules: parse_robots_txt 返回的规则

    Returns:
        True 允许,False 禁止
    """
    longest_disallow_len = -1
    longest_allow_len = -1

    for pattern in rules["disallow"]:
        if _match(pattern, path) and len(pattern) > longest_disallow_len:
            longest_disallow_len = len(pattern)

    for pattern in rules["allow"]:
        if _match(pattern, path) and len(pattern) > longest_allow_len:
            longest_allow_len = len(pattern)

    if longest_allow_len > longest_disallow_len:
        return True
    if longest_disallow_len > longest_allow_len:
        return False
    if longest_allow_len == -1 and longest_disallow_len == -1:
        return True
    return longest_allow_len >= longest_disallow_len


def _match(pattern: str, path: str) -> bool:
    """判断 path 是否匹配 robots.txt 规则 pattern.

    - 末尾 / 前缀匹配 (如 '/private/' 匹配 '/private/secret')
    - 否则精确匹配或带后续 / 匹配
    """
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return path == pattern or path.startswith(pattern + "/")


class RobotsChecker:
    """异步 robots.txt 检查器,带缓存."""

    def __init__(self, user_agent: str = "EcomRadar", cache_ttl: float = 60.0):
        """初始化.

        Args:
            user_agent: 标识 EcomRadar 的 UA
            cache_ttl: 缓存时间(秒)
        """
        from typing import Literal
        self.user_agent = user_agent
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, dict[str, list[str]] | None]] = {}
        self._lock = asyncio.Lock()

    async def _fetch_robots(self, host_url: str) -> FetchResult:
        """抓取 host 的 robots.txt.

        Returns:
            - str: 抓取到的内容(200)
            - 'NOT_FOUND': 404,允许抓取(按 RFC 9309 惯例)
            - 'ERROR': 网络错误,保守拒绝
        """
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(
                    f"{host_url}/robots.txt",
                    headers={"User-Agent": self.user_agent},
                )
                if response.status_code == 200:
                    return response.text
                if response.status_code == 404:
                    return "NOT_FOUND"
        except Exception:
            return "ERROR"
        return "ERROR"

    def _parse_host(self, url: str) -> tuple[str, str] | None:
        """抽取 (scheme://netloc, path) 形式."""
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return None
            return f"{parsed.scheme}://{parsed.netloc}", parsed.path or "/"
        except Exception:
            return None

    async def is_allowed(self, url: str) -> bool:
        """检查 URL 是否可抓取.

        Args:
            url: 目标 URL

        Returns:
            True 允许抓取,False 禁止
        """
        parsed = self._parse_host(url)
        if parsed is None:
            return False
        host_url, path = parsed

        now = time.monotonic()
        if host_url in self._cache:
            ts, rules = self._cache[host_url]
            if now - ts < self.cache_ttl:
                if rules is None:
                    return True
                return is_path_allowed(path, rules)

        try:
            async with self._lock:
                now = time.monotonic()
                if host_url in self._cache:
                    ts, rules = self._cache[host_url]
                    if now - ts < self.cache_ttl:
                        if rules is None:
                            return True
                        return is_path_allowed(path, rules)

                text = await self._fetch_robots(host_url)
                if text == "ERROR":
                    return False
                if text == "NOT_FOUND" or text is None:
                    self._cache[host_url] = (now, None)
                    return True
                rules = parse_robots_txt(text)
                self._cache[host_url] = (now, rules)
                return is_path_allowed(path, rules)
        except Exception:
            return False
