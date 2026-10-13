"""三级降级抓取策略.

降级链:
1. direct: 直接 HTTP 抓取
2. jina: r.jina.ai 第三方 reader 兜底
3. mock: 本地虚构数据兜底

设计目标:
- 单个 URL 抓取失败不影响整体流程
- 明确标注降级层级,便于审计与质量回溯
- 失败快速失败(fail-fast),不浪费超时时间
"""
from dataclasses import dataclass, field
from typing import Awaitable, Callable


FALLBACK_LEVELS: list[str] = ["direct", "jina", "mock"]


@dataclass
class FallbackResult:
    """降级抓取结果."""
    url: str
    content: str
    level: str  # 'direct' / 'jina' / 'mock'
    success_level: str  # 最终成功的层级
    attempts: list[str] = field(default_factory=list)
    error_messages: list[str] = field(default_factory=list)


async def fetch_with_fallback(
    url: str,
    direct_fetch: Callable[[str], Awaitable[str]],
    jina_fetch: Callable[[str], Awaitable[str]],
    mock_fetch: Callable[[str], Awaitable[str]],
) -> FallbackResult:
    """按 direct → jina → mock 顺序尝试抓取.

    Args:
        url: 目标 URL
        direct_fetch: 直接抓取 coroutine,返回 HTML 文本
        jina_fetch: jina reader 抓取 coroutine
        mock_fetch: mock 数据 coroutine,返回预定义内容

    Returns:
        FallbackResult 含最终内容、来源层级、尝试链
    """
    result = FallbackResult(url=url, content="", level="mock", success_level="mock")

    for fetcher, level in [
        (direct_fetch, "direct"),
        (jina_fetch, "jina"),
        (mock_fetch, "mock"),
    ]:
        result.attempts.append(level)
        try:
            content = await fetcher(url)
            if content and content.strip():
                result.content = content
                result.success_level = level
                result.level = level
                return result
        except Exception as e:
            result.error_messages.append(f"{level}: {type(e).__name__}: {e}")

    return result
