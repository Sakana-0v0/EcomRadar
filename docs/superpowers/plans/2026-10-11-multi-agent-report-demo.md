# Multi-Agent Report System - First Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现从 URL 输入到结构化研报输出的完整核心链路 Demo，支持 SSE 流式交付

**Architecture:** 基于 LangGraph 状态机实现 Scraper → Extractor → Retriever → Writer ↔ Evaluator 的 Generator-Evaluator 循环。节点间通过 TypedDict 传递状态，所有 I/O 操作使用 async/await，服务逻辑下沉至 `app/services/`。

**Tech Stack:** Python 3.10+, LangGraph, FastAPI, Qdrant-Client, httpx, Asyncio

**Spec:** `projext_description.txt`（项目根目录，项目说明中有拼写）

---

## Global Constraints

- Python 3.10+
- 所有状态使用 TypedDict / Pydantic，禁止裸 dict
- 所有 I/O（网络、向量DB、LLM）必须 async/await
- 节点不得直接写爬虫/检索逻辑，必须调用 `app/services/`
- 质量门控：`quality_score >= 75` 通过，否则 `retry_count < 2` 时回退 Writer

---

## File Structure

```
app/
├── main.py                          # FastAPI 入口（不变）
├── core/
│   ├── config.py                   # Pydantic Settings 配置
│   └── logging.py                  # 日志配置
├── graph/
│   ├── state.py                    # GraphState TypedDict 定义
│   ├── workflow.py                 # StateGraph 构建与编译
│   ├── nodes/
│   │   ├── scraper_node.py         # 调用 scraper service
│   │   ├── extractor_node.py       # 调用 chunker service
│   │   ├── rag_node.py             # 调用 vector_store service
│   │   ├── writer_node.py          # 调用 LLM 生成报告
│   │   └── evaluator_node.py       # 调用 evaluator service
│   └── edges/
│       └── router.py               # 条件边路由
├── services/
│   ├── scraper.py                  # asyncio httpx 异步采集
│   ├── chunker.py                  # 语义分块逻辑
│   ├── vector_store.py             # Qdrant 客户端封装
│   └── evaluator.py                # 评分计算逻辑
├── api/v1/endpoints/
│   ├── report.py                   # /report/generate 接口（SSE）
│   └── health.py                   # /health 接口
└── schemas/
    ├── request.py                  # ReportRequest
    └── response.py                 # ReportResponse

tests/
├── test_scraper.py                 # 异步采集测试
├── test_chunker.py                 # 分块逻辑测试
└── test_graph.py                   # 状态图流转测试
```

---

## Task Map

| Task | 组件 | 关键产出 |
|------|------|----------|
| 1 | GraphState 定义 | `app/graph/state.py` |
| 2 | Scraper 服务 + 节点 | `app/services/scraper.py`, `app/graph/nodes/scraper_node.py` |
| 3 | Chunker 服务 + Extractor 节点 | `app/services/chunker.py`, `app/graph/nodes/extractor_node.py` |
| 4 | VectorStore 服务 + RAG 节点 | `app/services/vector_store.py`, `app/graph/nodes/rag_node.py` |
| 5 | Writer 节点 | `app/graph/nodes/writer_node.py` |
| 6 | Evaluator 服务 + 节点 + 路由边 | `app/services/evaluator.py`, `app/graph/nodes/evaluator_node.py`, `app/graph/edges/router.py` |
| 7 | Workflow 组装 | `app/graph/workflow.py` |
| 8 | SSE 接口 | `app/api/v1/endpoints/report.py` |
| 9 | 单元测试 | `tests/` |
| 10 | 配置文件完善 | `app/core/config.py`, `app/core/logging.py` |

---

## Task Details

### Task 1: GraphState 定义

**Files:**
- Create: `app/graph/state.py`

**Interfaces:**
- Produces: `GraphState` TypedDict (被所有节点消费)

- [ ] **Step 1: 定义 GraphState TypedDict**

```python
from typing import TypedDict, Optional

class GraphState(TypedDict):
    urls: list[str]
    scraped_content: dict[str, str]
    chunks: list[str]
    context_docs: list[str]
    report: str
    quality_score: int
    retry_count: int
    is_degraded: bool
    error_messages: list[str]
```

- [ ] **Step 2: Commit**

---

### Task 2: Scraper 服务 + 节点

**Files:**
- Create: `app/services/scraper.py`
- Create: `app/graph/nodes/scraper_node.py`

**Interfaces:**
- Consumes: `GraphState["urls"]`
- Produces: `GraphState["scraped_content"]`

- [ ] **Step 1: 写测试**

```python
# tests/test_scraper.py
import pytest

@pytest.mark.asyncio
async def test_scrape_single_url():
    from app.services.scraper import scrape_urls
    result = await scrape_urls(["https://example.com"])
    assert "https://example.com" in result
    assert len(result["https://example.com"]) > 0
```

- [ ] **Step 2: Run test (expect FAIL)**

- [ ] **Step 3: 实现 scraper.py**

```python
# app/services/scraper.py
import asyncio
import httpx
from typing import AsyncGenerator

async def scrape_urls(urls: list[str], timeout: float = 5.0) -> dict[str, str]:
    """异步并发抓取多个 URL，返回 {url: content}"""
    async def fetch_one(client: httpx.AsyncClient, url: str) -> tuple[str, str]:
        try:
            response = await client.get(url, timeout=timeout)
            response.raise_for_status()
            text = response.text
            text = _clean_html(text)
            return url, text
        except Exception as e:
            return url, ""

    async with httpx.AsyncClient() as client:
        tasks = [fetch_one(client, url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {url: content for url, content in results if isinstance(content, str)}
```

- [ ] **Step 4: Run test (expect PASS)**

- [ ] **Step 5: 实现 scraper_node.py**

```python
# app/graph/nodes/scraper_node.py
from app.graph.state import GraphState
from app.services.scraper import scrape_urls

async def scraper_node(state: GraphState) -> GraphState:
    urls = state.get("urls", [])
    scraped = await scrape_urls(urls)
    return {"scraped_content": scraped}
```

- [ ] **Step 6: Commit**

---

### Task 3: Chunker 服务 + Extractor 节点

**Files:**
- Create: `app/services/chunker.py`
- Create: `app/graph/nodes/extractor_node.py`

**Interfaces:**
- Consumes: `GraphState["scraped_content"]`
- Produces: `GraphState["chunks"]`

- [ ] **Step 1: 写测试**

```python
# tests/test_chunker.py
def test_chunk_by_sentence():
    from app.services.chunker import chunk_text
    text = "这是第一句。这是第二句。这是第三句。"
    chunks = chunk_text(text, chunk_size=50, overlap_size=8)
    assert len(chunks) > 1
```

- [ ] **Step 2: Run test (expect FAIL)**

- [ ] **Step 3: 实现 chunker.py**

```python
# app/services/chunker.py
import re
from typing import Iterator

def chunk_text(text: str, chunk_size: int = 600, overlap_size: int = 90) -> list[str]:
    """按中文句号切分语义块，添加重叠窗口"""
    sentences = re.split(r'(?<=[。！？])', text)
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) <= chunk_size:
            current += sentence
        else:
            if current:
                chunks.append(current)
            overlap = current[-overlap_size:] if len(current) > overlap_size else current
            current = overlap + sentence
    if current:
        chunks.append(current)
    return chunks
```

- [ ] **Step 4: Run test (expect PASS)**

- [ ] **Step 5: 实现 extractor_node.py**

```python
# app/graph/nodes/extractor_node.py
from app.graph.state import GraphState
from app.services.chunker import chunk_text

def extractor_node(state: GraphState) -> GraphState:
    scraped = state.get("scraped_content", {})
    all_chunks = []
    for content in scraped.values():
        if content:
            chunks = chunk_text(content)
            all_chunks.extend(chunks)
    return {"chunks": all_chunks}
```

- [ ] **Step 6: Commit**

---

### Task 4: VectorStore 服务 + RAG 节点

**Files:**
- Create: `app/services/vector_store.py`
- Create: `app/graph/nodes/rag_node.py`

**Interfaces:**
- Consumes: `GraphState["chunks"]`
- Produces: `GraphState["context_docs"]`

- [ ] **Step 1: 写测试**

```python
# tests/test_vector_store.py
def test_retrieve_top_k():
    from app.services.vector_store import retrieve_context
    docs = retrieve_context("人工智能", top_k=3)
    assert len(docs) <= 3
```

- [ ] **Step 2: Run test (expect FAIL)**

- [ ] **Step 3: 实现 vector_store.py**

```python
# app/services/vector_store.py
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

_client = None

def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(host="localhost", port=6333)
    return _client

def retrieve_context(query: str, top_k: int = 5) -> list[str]:
    """向量检索召回 Top-K 上下文"""
    client = get_client()
    try:
        results = client.search(
            collection_name="reports",
            query_vector=query,
            limit=top_k
        )
        return [result.payload.get("text", "") for result in results]
    except Exception:
        return []
```

- [ ] **Step 4: Run test (expect PASS 或 SKIP 如果 Qdrant 不可用)**

- [ ] **Step 5: 实现 rag_node.py**

```python
# app/graph/nodes/rag_node.py
from app.graph.state import GraphState
from app.services.vector_store import retrieve_context

def rag_node(state: GraphState) -> GraphState:
    chunks = state.get("chunks", [])
    if not chunks:
        return {"context_docs": []}
    topic = chunks[0][:100]
    context = retrieve_context(topic, top_k=5)
    return {"context_docs": context}
```

- [ ] **Step 6: Commit**

---

### Task 5: Writer 节点

**Files:**
- Create: `app/graph/nodes/writer_node.py`

**Interfaces:**
- Consumes: `GraphState["scraped_content"]`, `GraphState["context_docs"]`, `GraphState["retry_count"]`
- Produces: `GraphState["report"]`

- [ ] **Step 1: 写测试**

```python
# tests/test_writer.py
def test_writer_node_increments_retry():
    from app.graph.nodes.writer_node import writer_node
    from app.graph.state import GraphState
    state: GraphState = {
        "urls": [],
        "scraped_content": {"http://a.com": "内容"},
        "chunks": [],
        "context_docs": [],
        "report": "",
        "quality_score": 0,
        "retry_count": 0,
        "is_degraded": False,
        "error_messages": []
    }
    result = writer_node(state)
    assert result["retry_count"] == 1
    assert len(result["report"]) > 0
```

- [ ] **Step 2: Run test (expect FAIL)**

- [ ] **Step 3: 实现 writer_node.py（Demo 用 mock LLM）**

```python
# app/graph/nodes/writer_node.py
from app.graph.state import GraphState

async def writer_node(state: GraphState) -> GraphState:
    retry_count = state.get("retry_count", 0)
    scraped = state.get("scraped_content", {})
    context = state.get("context_docs", [])

    content_summary = "".join(scraped.values())[:500]
    context_summary = "".join(context)[:200]

    report = f"""# 研究报告

## 核心要点
基于 {len(scraped)} 个信息源生成

## 内容摘要
{content_summary}

## 上下文参考
{context_summary}

---
*本报告为 Demo 版本（重试次数: {retry_count）}*
"""
    return {
        "report": report,
        "retry_count": retry_count + 1
    }
```

- [ ] **Step 4: Run test (expect PASS)**

- [ ] **Step 5: Commit**

---

### Task 6: Evaluator 服务 + 节点 + 路由边

**Files:**
- Create: `app/services/evaluator.py`
- Create: `app/graph/nodes/evaluator_node.py`
- Create: `app/graph/edges/router.py`

**Interfaces:**
- Consumes: `GraphState["report"]`
- Produces: `GraphState["quality_score"]`

- [ ] **Step 1: 写测试**

```python
# tests/test_evaluator.py
def test_evaluate_report():
    from app.services.evaluator import evaluate_report
    score = evaluate_report("# 报告\n内容")
    assert 0 <= score <= 100
    assert isinstance(score, int)
```

- [ ] **Step 2: Run test (expect FAIL)**

- [ ] **Step 3: 实现 evaluator.py**

```python
# app/services/evaluator.py
import re

def evaluate_report(report: str) -> int:
    """评估报告质量：事实忠实度(40%) + 结构完整性(30%) + 逻辑连贯性(30%)"""
    if not report:
        return 0

    score = 0

    has_summary = bool(re.search(r'摘要|总结|核心', report))
    has_structure = bool(re.search(r'##\s+\w+', report))
    has_content = len(report) > 100

    score += 40 if has_summary else 20
    score += 30 if has_structure else 15
    score += 30 if has_content else 10

    return min(100, max(0, score))
```

- [ ] **Step 4: Run test (expect PASS)**

- [ ] **Step 5: 实现 evaluator_node.py**

```python
# app/graph/nodes/evaluator_node.py
from app.graph.state import GraphState
from app.services.evaluator import evaluate_report

def evaluator_node(state: GraphState) -> GraphState:
    report = state.get("report", "")
    score = evaluate_report(report)
    return {"quality_score": score}
```

- [ ] **Step 6: 实现 router.py（条件边）**

```python
# app/graph/edges/router.py
from app.graph.state import GraphState

def should_retry(state: GraphState) -> str:
    quality = state.get("quality_score", 0)
    retry = state.get("retry_count", 0)
    if quality >= 75 or retry >= 2:
        return "end"
    return "rewrite"
```

- [ ] **Step 7: Commit**

---

### Task 7: Workflow 组装

**Files:**
- Modify: `app/graph/workflow.py`

**Interfaces:**
- Consumes: 所有 nodes 和 edges
- Produces: `app.graph.workflow.graph` (compiled StateGraph)

- [ ] **Step 1: 实现 workflow.py**

```python
# app/graph/workflow.py
from langgraph.graph import StateGraph, END
from app.graph.state import GraphState
from app.graph.nodes import (
    scraper_node,
    extractor_node,
    rag_node,
    writer_node,
    evaluator_node
)
from app.graph.edges.router import should_retry

def build_workflow() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("scraper", scraper_node)
    graph.add_node("extractor", extractor_node)
    graph.add_node("rag", rag_node)
    graph.add_node("writer", writer_node)
    graph.add_node("evaluator", evaluator_node)

    graph.set_entry_point("scraper")
    graph.add_edge("scraper", "extractor")
    graph.add_edge("extractor", "rag")
    graph.add_edge("rag", "writer")
    graph.add_edge("writer", "evaluator")

    graph.add_conditional_edges(
        "evaluator",
        should_retry,
        {"rewrite": "writer", "end": END}
    )

    return graph.compile()

graph = build_workflow()
```

- [ ] **Step 2: 写测试验证状态图可以编译运行**

```python
# tests/test_graph.py
def test_workflow_compiles():
    from app.graph.workflow import graph
    assert graph is not None

@pytest.mark.asyncio
async def test_workflow_run():
    from app.graph.workflow import graph
    from app.graph.state import GraphState
    state: GraphState = {
        "urls": ["https://example.com"],
        "scraped_content": {},
        "chunks": [],
        "context_docs": [],
        "report": "",
        "quality_score": 0,
        "retry_count": 0,
        "is_degraded": False,
        "error_messages": []
    }
    result = await graph.ainvoke(state)
    assert "report" in result
```

- [ ] **Step 3: Run tests (expect PASS)**

- [ ] **Step 4: Commit**

---

### Task 8: SSE 接口

**Files:**
- Modify: `app/api/v1/endpoints/report.py`

**Interfaces:**
- Consumes: Workflow graph
- Produces: SSE 流式响应

- [ ] **Step 1: 实现 report.py**

```python
# app/api/v1/endpoints/report.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from app.graph.state import GraphState
from app.graph.workflow import graph
from app.schemas.request import ReportRequest

router = APIRouter()

@router.post("/generate")
async def generate_report(request: ReportRequest):
    async def event_stream():
        initial_state: GraphState = {
            "urls": request.urls,
            "scraped_content": {},
            "chunks": [],
            "context_docs": [],
            "report": "",
            "quality_score": 0,
            "retry_count": 0,
            "is_degraded": False,
            "error_messages": []
        }

        async for event in graph.astream(initial_state):
            for node_name, node_data in event.items():
                if "report" in node_data and node_data["report"]:
                    yield {"event": "report", "data": node_data["report"]}
            if "quality_score" in str(event):
                score = node_data.get("quality_score", 0)
                yield {"event": "score", "data": str(score)}

        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_stream())
```

- [ ] **Step 2: 实现 request.py schema**

```python
# app/schemas/request.py
from pydantic import BaseModel
from typing import list

class ReportRequest(BaseModel):
    urls: list[str]
```

- [ ] **Step 3: 实现 response.py schema**

```python
# app/schemas/response.py
from pydantic import BaseModel

class ReportResponse(BaseModel):
    report: str
    quality_score: int
    retry_count: int
    is_degraded: bool
```

- [ ] **Step 4: Commit**

---

### Task 9: 配置文件完善

**Files:**
- Modify: `app/core/config.py`
- Modify: `app/core/logging.py`

- [ ] **Step 1: 实现 config.py**

```python
# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str = ""
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
```

- [ ] **Step 2: 实现 logging.py**

```python
# app/core/logging.py
import logging
import sys

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
```

- [ ] **Step 3: Commit**

---

### Task 10: 主入口更新

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: 更新 main.py**

```python
# app/main.py
from fastapi import FastAPI
from app.api.v1.router import router as v1_router
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(title="Multi-Agent Report System")
app.include_router(v1_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 2: Commit**

---

## 自检清单

- [ ] Spec 覆盖率：FR-01~FR-12 全部覆盖
- [ ] 无占位符（无 TBD/TODO）
- [ ] 类型一致性：GraphState 在所有任务中一致使用
- [ ] 异步一致性：节点函数命名符合 async/await 约定
- [ ] 服务下沉：`app/services/` 包含所有业务逻辑，节点仅编排调用

---

## 执行方式

**Plan complete and saved to `docs/superpowers/plans/2026-10-11-multi-agent-report-demo.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
