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
- httpx (异步 HTTP)
- Asyncio

## 目录结构

```
app/
├── main.py                  # FastAPI 主入口
├── core/                    # 配置与日志
│   ├── config.py            # Pydantic Settings 环境变量
│   └── logging.py           # 日志配置
├── graph/                   # LangGraph 核心
│   ├── state.py             # GraphState TypedDict
│   ├── workflow.py          # StateGraph 构建与编译
│   ├── nodes/               # 各 Agent 节点
│   │   ├── scraper_node.py
│   │   ├── extractor_node.py
│   │   ├── rag_node.py
│   │   ├── writer_node.py
│   │   └── evaluator_node.py
│   └── edges/
│       └── router.py        # 条件边路由
├── services/                # 底层业务服务
│   ├── scraper.py           # asyncio httpx 异步采集
│   ├── chunker.py          # 语义分块
│   ├── vector_store.py      # Qdrant 客户端
│   └── evaluator.py        # 质量评分
├── api/v1/endpoints/       # 接口路由
│   ├── report.py           # SSE 流式研报生成
│   └── health.py          # 健康检查
└── schemas/                # Pydantic 模型
    ├── request.py
    └── response.py
```

## 开发命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest tests/ -v

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Docker Compose
docker-compose up --build
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/health` | GET | 健康检查 |
| `/api/v1/report/generate` | POST | 研报生成（SSE 流式） |
| `/` | GET | 根路径 |

## 质量评分规则

- 事实忠实度 (40%): 是否包含摘要/核心要点
- 结构完整性 (30%): 是否有 markdown 标题层级
- 逻辑连贯性 (30%): 内容是否超过 100 字符
