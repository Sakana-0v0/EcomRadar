"""元数据过滤器.

按 platform / category / 时间范围 / 自定义字段过滤.
"""
from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass
class FilterCriteria:
    """过滤条件."""
    platform: Optional[Union[str, list[str]]] = None
    category: Optional[Union[str, list[str]]] = None
    source: Optional[Union[str, list[str]]] = None
    min_timestamp: Optional[float] = None
    max_timestamp: Optional[float] = None
    custom: dict = field(default_factory=dict)


class MetadataFilter:
    """元数据过滤器."""

    def filter(
        self,
        documents: list[dict],
        criteria: Optional[FilterCriteria] = None,
    ) -> list[dict]:
        """根据条件过滤文档.

        Args:
            documents: 待过滤文档列表
            criteria: 过滤条件,None 全部返回

        Returns:
            过滤后的文档列表(保持原顺序)
        """
        if criteria is None:
            return list(documents)

        result: list[dict] = []
        for doc in documents:
            if not self._matches(doc, criteria):
                continue
            result.append(doc)
        return result

    def _matches(self, doc: dict, c: FilterCriteria) -> bool:
        if c.platform is not None:
            if isinstance(c.platform, list):
                if doc.get("platform") not in c.platform:
                    return False
            else:
                if doc.get("platform") != c.platform:
                    return False

        if c.category is not None:
            if isinstance(c.category, list):
                if doc.get("category") not in c.category:
                    return False
            else:
                if doc.get("category") != c.category:
                    return False

        if c.source is not None:
            if isinstance(c.source, list):
                if doc.get("source") not in c.source:
                    return False
            else:
                if doc.get("source") != c.source:
                    return False

        ts = doc.get("timestamp")
        if ts is not None:
            if c.min_timestamp is not None and ts < c.min_timestamp:
                return False
            if c.max_timestamp is not None and ts > c.max_timestamp:
                return False

        for key, expected in c.custom.items():
            if doc.get(key) != expected:
                return False

        return True
