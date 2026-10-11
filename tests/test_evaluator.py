from app.services.evaluator import evaluate_report
from app.graph.edges.router import should_retry
from app.graph.state import GraphState


def test_evaluate_report():
    score = evaluate_report("# 报告\n内容")
    assert 0 <= score <= 100
    assert isinstance(score, int)


def test_evaluate_report_empty():
    score = evaluate_report("")
    assert score == 0


def test_evaluate_report_full_score():
    report = """## 摘要
这是核心要点
## 内容
这是一段很长的内容，超过了一百个字符的最低要求，以便满足内容评估的标准。本测试需要确保内容足够长，以便通过质量评估的字符数检查。添加更多文字以确保总长度超过一百个字符的要求。"""
    score = evaluate_report(report)
    assert score == 100


def test_should_retry_rewrite():
    state: GraphState = {
        "urls": [], "scraped_content": {}, "chunks": [],
        "context_docs": [], "report": "", "quality_score": 60,
        "retry_count": 0, "is_degraded": False, "error_messages": []
    }
    assert should_retry(state) == "rewrite"


def test_should_retry_end():
    state: GraphState = {
        "urls": [], "scraped_content": {}, "chunks": [],
        "context_docs": [], "report": "", "quality_score": 80,
        "retry_count": 1, "is_degraded": False, "error_messages": []
    }
    assert should_retry(state) == "end"


def test_should_retry_max_retries():
    state: GraphState = {
        "urls": [], "scraped_content": {}, "chunks": [],
        "context_docs": [], "report": "", "quality_score": 60,
        "retry_count": 2, "is_degraded": False, "error_messages": []
    }
    assert should_retry(state) == "end"


def test_should_retry_high_quality():
    state: GraphState = {
        "urls": [], "scraped_content": {}, "chunks": [],
        "context_docs": [], "report": "", "quality_score": 90,
        "retry_count": 0, "is_degraded": False, "error_messages": []
    }
    assert should_retry(state) == "end"