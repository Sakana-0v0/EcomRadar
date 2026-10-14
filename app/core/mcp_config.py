"""MCP Config (Phase 7 完整实现, 此处为接口占位).

Phase 5 阶段先建立接口, 让 Publisher Node 可以无错编译.
Phase 7 会接入 Notion + 飞书 Client.
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class Publisher(Protocol):
    """Publisher 抽象接口."""

    channel_name: str

    async def publish(self, title: str, content: str, metadata: dict) -> bool:
        """发布内容, 成功返回 True."""
        ...


_PUBLISHERS: list[Publisher] = []


def register_publisher(publisher: Publisher) -> None:
    """注册一个 Publisher (Phase 7 接入)."""
    _PUBLISHERS.append(publisher)


def get_publishers() -> list[Publisher]:
    """获取已注册的 Publisher 列表."""
    return list(_PUBLISHERS)


def clear_publishers() -> None:
    """清空 Publisher 注册 (用于测试)."""
    global _PUBLISHERS
    _PUBLISHERS = []
