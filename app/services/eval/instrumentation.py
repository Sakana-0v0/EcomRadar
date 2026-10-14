"""端到端埋点 - Span 计时 + Counter 计数.

用途:
- 评测时记录每个节点的耗时
- 收集 tool call 成功/失败次数
- 导出 JSON 报告 (供 benchmark 对比)

设计原则:
- 零依赖 (无 OpenTelemetry 等重组件)
- 同步/异步统一
- 全局单例 + 显式实例双模式
"""
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Span:
    """单次操作的计时段."""
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def stop(self) -> None:
        self.end_time = time.monotonic()
        self.duration_ms = (self.end_time - self.start_time) * 1000

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }
        if self.error:
            d["error"] = self.error
        return d


@dataclass
class Counter:
    """计数器."""
    name: str
    value: int = 0
    metadata: dict = field(default_factory=dict)

    def increment(self, by: int = 1) -> None:
        self.value += by

    def to_dict(self) -> dict:
        return asdict(self)


class Instrumentation:
    """埋点收集器."""

    def __init__(self) -> None:
        self.spans: list[Span] = []
        self.counters: dict[str, Counter] = {}

    def create_span(self, name: str, metadata: Optional[dict] = None) -> Span:
        """创建 Span (调用方负责 stop)."""
        span = Span(name=name, start_time=time.monotonic(), metadata=metadata or {})
        self.spans.append(span)
        return span

    def increment_counter(self, name: str, by: int = 1) -> Counter:
        """递增计数器."""
        if name not in self.counters:
            self.counters[name] = Counter(name=name)
        self.counters[name].increment(by)
        return self.counters[name]

    def export(self) -> dict:
        """导出所有埋点数据."""
        return {
            "spans": [s.to_dict() for s in self.spans],
            "counters": {k: v.to_dict() for k, v in self.counters.items()},
        }

    def reset(self) -> None:
        self.spans = []
        self.counters = {}


_DEFAULT: Optional[Instrumentation] = None


def get_default_instrumentation() -> Instrumentation:
    """获取全局默认埋点器 (单例)."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Instrumentation()
    return _DEFAULT


def reset_default_instrumentation() -> None:
    """重置默认埋点器 (测试用)."""
    global _DEFAULT
    _DEFAULT = None


@contextmanager
def trace_span(instrumentation: Instrumentation, name: str, metadata: Optional[dict] = None):
    """上下文管理器: 自动 stop + 异常捕获."""
    span = instrumentation.create_span(name, metadata)
    try:
        yield span
    except Exception as e:
        span.error = f"{type(e).__name__}: {e}"
        raise
    finally:
        span.stop()
