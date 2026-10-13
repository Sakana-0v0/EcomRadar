# 多智能体垂直资讯聚合与研报生成系统

基于 LangGraph 多智能体协同状态机架构的自动化研报系统，实现从外部资讯链接输入到结构化专业研报交付的全流程无人值守运行。

## 系统架构

```
开始 -> 爬取资讯（url）-> 语义分块与噪声过滤 -> 检索增强 -> 研报生成 -> 质量评估 -> 流式交付 -> 结束
[START] → [Scraper] → [Extractor] → [Retriever] → [Writer] ↔ [Evaluator] → [END]
                                                    ↑                ↓
                                                    ←── retry ≤ 2 ───
```

LangGraph 状态机驱动的 Generator-Evaluator 循环：
- **Scraper**: 多源异步高并发采集
- **Extractor**: 语义分块与噪声过滤
- **Retriever**: Qdrant 混合检索增强（RAG）
- **Writer**: 多维结构化研报撰写
- **Evaluator**: 质量评估与循环收敛控制

**质量门控规则**：
- `quality_score ≥ 75` → 流程结束
- `quality_score < 75` 且 `retry_count < 2` → 回退至 Writer 重试
- `retry_count ≥ 2` → 强制收敛退出

## 核心功能

| 模块 | 功能说明 |
|------|----------|
| **资讯采集** | 多 URL 异步并发拉取，5 秒超时容错，自动剔除 HTML 噪声 |
| **语义分块** | 段落/句号切分，500~800 Tokens，含 15% 重叠窗口 |
| **检索增强** | Dense + Sparse 混合检索，Top-5 上下文召回 |
| **研报生成** | Executive Summary / Key Facts / Impact Analysis / Outlook & Risks |
| **质量评估** | 事实忠实度(40%) + 结构完整性(30%) + 逻辑连贯性(30%) |
| **流式交付** | SSE 流式推流，端到端 8~12 秒 |

## 技术栈

- Python 3.10+
- **LangGraph**: 多智能体状态机
- **FastAPI**: REST API + SSE 流式接口
- **Qdrant-Client**: 向量数据库
- **Asyncio**: 异步高并发

## 目录结构

```
app/
├── main.py                  # FastAPI 主入口
├── core/                    # 配置与日志
│   ├── config.py            # 环境变量（API 密钥、Qdrant 地址）
│   └── logging.py           # 日志配置
├── graph/                   # LangGraph 核心逻辑
│   ├── state.py             # GraphState 共享状态定义
│   ├── workflow.py          # 状态图构建与条件边
│   ├── nodes/               # 各 Agent 节点
│   │   ├── scraper_node.py  # 资讯抓取调度
│   │   ├── extractor_node.py# 内容提炼与分块
│   │   ├── rag_node.py     # 向量检索与召回
│   │   └── writer_node.py  # 结构化研报撰写
│   └── edges/
│       └── router.py        # 条件边路由逻辑
├── services/                # 底层业务服务
│   ├── scraper.py           # Asyncio 异步采集
│   ├── chunker.py          # 语义分块
│   ├── vector_store.py      # Qdrant 客户端封装
│   └── evaluator.py        # 质量评分计算
├── api/v1/endpoints/       # 接口路由
│   ├── report.py           # 研报生成（SSE 流式）
│   └── health.py          # 健康检查
└── schemas/                # Pydantic 模型
    ├── request.py
    └── response.py

tests/                      # 测试用例
docker-compose.yml          # 容器编排（FastAPI + Qdrant）
Dockerfile                  # 镜像构建
requirements.txt            # 依赖清单
.env.example               # 环境变量模板
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入 API 密钥和 Qdrant 配置
```

### 3. 启动服务

**本地开发**：
```bash
uvicorn app.main:app --reload
```

**Docker Compose**：
```bash
docker-compose up --build
```

### 4. 调用接口

```bash
# 健康检查
curl http://localhost:8000/api/v1/health

# 生成研报（SSE 流式）
curl -X POST http://localhost:8000/api/v1/report/generate \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com/article"]}'
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/health` | GET | 容器探活 |
| `/api/v1/report/generate` | POST | 研报生成（支持 SSE 流式） |

## 性能指标

- 端到端交付时延：8~12 秒（万字级资讯）
- 单任务采集并发：≥ 10 个独立 URL
- 网络 I/O 超时：5 秒

## 相关文档

- [AGENTS.md](./AGENTS.md) - Agent 开发规范与编码约束
- `app/graph/` - LangGraph 状态机核心实现
- `app/services/` - 底层服务层封装
