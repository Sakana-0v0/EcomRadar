# Multi-Agent Report System

## 架构

- **框架**: LangGraph 状态机（Generator-Evaluator 循环）
- **流程**: Scraper → Extractor → Retriever → Writer ↔ Evaluator
- **质量门控**: 当 `quality_score < 75` 且 `retry_count < 2` 时重试 Writer

## 编码规范

- **强类型注解**: 所有状态必须使用 `typing`、`pydantic`、`TypedDict`，禁止裸 `dict`
- **异步优先**: 所有 I/O 操作（网络请求、向量数据库、LLM 调用）必须使用 `async/await`
- **分层隔离**: LangGraph Node 函数禁止直接书写爬虫或检索逻辑，必须调用 `app/services/` 下封装的服务
- **单文件职责**: 每个 Node 独立为一个文件，禁止将所有 Agent 逻辑堆砌在单个 `workflow.py` 中

## 技术栈

- Python 3.10+
- LangGraph
- FastAPI + SSE 流式推流
- Qdrant-Client (向量数据库)
- Asyncio

## 目录结构

```
app/
  nodes/       # LangGraph 节点实现（每个节点一个文件）
  services/    # 底层服务层（爬虫、抽取器、检索器）
  schemas/     # Pydantic/TypedDict 状态定义
```

## 开发命令

*(项目脚手架创建后补充)*
