"""Instrumentation 单元测试.

端到端埋点:
- Span 计时 (start/stop)
- Counter (tool calls, errors)
- 导出 (JSON / 内存)
"""
import time
import pytest

from app.services.eval.instrumentation import (
    Span,
    Counter,
    Instrumentation,
    trace_span,
    get_default_instrumentation,
)


class TestSpan:
    def test_creation(self):
        span = Span(name="test", start_time=time.monotonic())
        assert span.name == "test"
        assert span.duration_ms is None

    def test_stop_records_duration(self):
        span = Span(name="test", start_time=time.monotonic())
        time.sleep(0.05)
        span.stop()
        assert span.duration_ms is not None
        assert span.duration_ms >= 30
        assert span.end_time is not None

    def test_to_dict(self):
        span = Span(name="test", start_time=1.0)
        span.stop()
        d = span.to_dict()
        assert d["name"] == "test"
        assert "duration_ms" in d


class TestCounter:
    def test_increment(self):
        c = Counter(name="errors")
        c.increment()
        c.increment(2)
        assert c.value == 3

    def test_to_dict(self):
        c = Counter(name="errors", value=5)
        d = c.to_dict()
        assert d["name"] == "errors"
        assert d["value"] == 5


class TestInstrumentation:
    def test_create_span(self):
        inst = Instrumentation()
        span = inst.create_span("scraper")
        assert span.name == "scraper"
        assert inst.spans == [span]

    def test_increment_counter(self):
        inst = Instrumentation()
        c = inst.increment_counter("errors")
        assert c.value == 1
        inst.increment_counter("errors")
        assert inst.counters["errors"].value == 2

    def test_export(self):
        inst = Instrumentation()
        with trace_span(inst, "test"):
            time.sleep(0.05)
        inst.increment_counter("calls")
        data = inst.export()
        assert len(data["spans"]) == 1
        assert data["counters"]["calls"]["value"] == 1
        assert data["counters"]["calls"]["name"] == "calls"
        assert data["spans"][0]["duration_ms"] is not None
        assert data["spans"][0]["duration_ms"] >= 30

    def test_reset(self):
        inst = Instrumentation()
        inst.increment_counter("x")
        inst.reset()
        assert inst.counters == {}
        assert inst.spans == []


class TestTraceSpanContextManager:
    def test_context_manager_records_span(self):
        inst = Instrumentation()
        with trace_span(inst, "ctx_test"):
            time.sleep(0.05)
        assert len(inst.spans) == 1
        assert inst.spans[0].name == "ctx_test"
        assert inst.spans[0].duration_ms is not None
        assert inst.spans[0].duration_ms >= 30

    def test_context_manager_records_exception(self):
        inst = Instrumentation()
        with pytest.raises(ValueError):
            with trace_span(inst, "ctx_err"):
                raise ValueError("test error")
        assert "test error" in inst.spans[0].error
        assert "ValueError" in inst.spans[0].error

    def test_get_default_returns_singleton(self):
        a = get_default_instrumentation()
        b = get_default_instrumentation()
        assert a is b
