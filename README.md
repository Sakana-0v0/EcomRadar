# EcomRadar

> 多智能体电商竞品监控研报系统 · LangGraph · MCP · Qdrant

从竞品商品 URL 输入到结构化研报交付的端到端自动化流水线,内置质量门控、断点续跑、混合检索、多渠道推送。

**项目状态**: 🚧 Phase 9 / 9(88.9%)| **测试**: 388 passed(100%)| **Commit**: `bd87157`

---

## 核心能力

| 能力 | 实现 | 量化指标 |
|------|------|----------|
| **多平台抓取** | 4 平台 + 三级降级链 | 成功率 95%+ |
| **混合检索** | BM25 + Dense + Rerank + Dedup | Recall@5 = 0.933 |
| **质量门控** | 5 维度评分 + 75 分阈值 + 2 次重试 | Rerank Top1 = 90% |
| **状态治理** | Checkpointer + HITL + 熔断 | 断点续跑 |
| **多租户** | AES-256 凭证 + Sliding Window 限流 | Token single-flight |
| **多渠道推送** | Notion + 飞书双通道 | MCP 协议 |
| **量化评测** | 50 条 Benchmark + 5 大指标 | Tool Call 100%,P50 2.6s |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  FastAPI Middleware Stack                                   │
│  TenantMiddleware (X-Tenant-ID) · RateLimitMiddleware      │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  LangGraph 6 节点状态机 (Checkpointer + interrupt_before)    │
│                                                             │
│  Scraper → Extractor → RAG → Writer → Evaluator ↻ Publisher │
│              ↓           ↓        ↓            ↓           │
│         混合检索      竞品周报  5维度评分    HITL 中断       │
│         BM25+Dense   4段式    75分门控     /resume 端点    │
│         +Rerank+Dedup                                       │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  Publisher 双通道                                            │
│  Notion API (Markdown→Blocks) · 飞书 OpenAPI (文档创建)      │
└─────────────────────────────────────────────────────────────┘
```

详细架构图: [docs/ARCHITECTURE_DIAGRAM.md](docs/ARCHITECTURE_DIAGRAM.md)

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入真实值(详见 docs/CREDENTIAL_SETUP_GUIDE.md)
```

**关键配置**:

| 变量 | 说明 | 必填 |
|------|------|------|
| `LLM_API_KEY` | LLM API 密钥 | ✅ |
| `ECOMRADAR_CREDENTIAL_KEY` | 凭证加密 Master Key | ✅ |
| `EMBED_API_KEY` | Embedding API 密钥 | ✅ |
| `NOTION_API_KEY` | Notion 集成密钥 | ❌ |
| `FEISHU_APP_ID` | 飞书应用 ID | ❌ |

生成 Master Key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. 启动服务

**本地开发**:
```bash
uvicorn app.main:app --reload
```

**Docker Compose**:
```bash
docker-compose up --build
```

### 4. 调用 API

```bash
# 健康检查(无需 tenant header)
curl http://localhost:8000/api/v1/health

# 生成竞品研报(SSE 流式)
curl -X POST http://localhost:8000/api/v1/report/generate \
  -H "X-Tenant-ID: tenant_1" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://item.jd.com/100012345678.html"]}'

# HITL 审批后恢复
curl -X POST http://localhost:8000/api/v1/report/{task_id}/resume \
  -H "X-Tenant-ID: tenant_1" \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

API 文档: http://localhost:8000/docs

---

## 目录结构

```
EcomRadar/
├── app/
│   ├── core/                    # 配置与基础设施
│   │   ├── config.py            # Pydantic Settings
│   │   ├── checkpointer.py      # Memory + Postgres 双后端
│   │   └── mcp_config.py        # Publisher 注册中心
│   ├── graph/                   # LangGraph 核心
│   │   ├── state.py             # GraphState (含 tenant_id)
│   │   ├── workflow.py          # 6 节点编译 + interrupt
│   │   ├── nodes/               # 6 个 Agent 节点
│   │   │   ├── scraper_node.py
│   │   │   ├── extractor_node.py
│   │   │   ├── rag_node.py
│   │   │   ├── writer_node.py
│   │   │   ├── evaluator_node.py
│   │   │   └── publisher_node.py    # HITL 触发点
│   │   └── edges/router.py      # 三向路由
│   ├── services/                # 业务服务层
│   │   ├── ecomradar/           # 抓取层
│   │   │   ├── rate_limiter.py      # 令牌桶
│   │   │   ├── robots_checker.py    # RFC 9309
│   │   │   ├── product_parser.py    # 4 平台 HTML
│   │   │   ├── fallback_strategy.py # 三级降级
│   │   │   └── scraper_v2.py
│   │   ├── retrieval/           # 检索层
│   │   │   ├── bm25_index.py        # BM25Plus
│   │   │   ├── hybrid_search.py     # BM25+Dense
│   │   │   ├── reranker.py          # 4 信号 Rerank
│   │   │   ├── metadata_filter.py   # 多维过滤
│   │   │   ├── semantic_dedup.py    # Jaccard+SimHash
│   │   │   └── retrieval_pipeline.py
│   │   ├── governance/          # 状态治理层
│   │   │   ├── retry_policy.py      # 指数退避+jitter
│   │   │   ├── circuit_breaker.py   # 三态熔断
│   │   │   ├── output_validator.py  # Pydantic 校验
│   │   │   └── state_recovery.py    # 断点续跑
│   │   ├── security/            # 安全层
│   │   │   ├── credential_store.py  # AES-256 加密
│   │   │   ├── rate_limiter.py      # Sliding Window
│   │   │   └── token_manager.py     # TTL 自动刷新
│   │   ├── publisher/           # 多渠道推送层
│   │   │   ├── notion_client.py
│   │   │   ├── feishu_client.py
│   │   │   └── markdown_to_blocks.py
│   │   └── eval/                # 评测层
│   │       ├── metrics.py           # EM/F1/ROUGE-L/Latency
│   │       ├── runner.py            # BenchmarkRunner
│   │       ├── llm_judge.py         # LLM-as-Judge
│   │       ├── ab_framework.py      # A/B 对比
│   │       └── instrumentation.py   # 端到端埋点
│   ├── schemas/                 # Pydantic 模型
│   │   ├── request.py
│   │   ├── response.py
│   │   └── ecom_report.py       # 竞品报告 Schema
│   ├── middleware/              # FastAPI 中间件
│   │   └── __init__.py          # Tenant + RateLimit
│   ├── api/v1/endpoints/        # API 路由
│   │   ├── report.py            # /generate /resume /status
│   │   └── health.py
│   └── main.py                  # FastAPI 入口
├── data/
│   ├── benchmark/               # 50 条 Benchmark
│   ├── kb_sources/              # 电商知识库
│   └── eval_results/            # 评测结果
├── docs/                        # 项目文档
│   ├── PROJECT_PROGRESS.md      # 进度追踪
│   ├── ARCHITECTURE_DIAGRAM.md  # 架构图
│   ├── HIGHLIGHTS.md            # 亮点汇总
│   ├── EVAL_RESULTS.md          # 量化报告
│   └── CREDENTIAL_SETUP_GUIDE.md
├── scripts/                     # 工具脚本
│   ├── run_benchmark.py
│   ├── run_retrieval_benchmark.py
│   └── setup_credentials.py
├── tests/                       # 388 个测试
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## 项目进度

| 阶段 | 内容 | 状态 | 测试 |
|------|------|------|------|
| Phase 1 | 业务预研文档 | ✅ | +7 |
| Phase 2 | 真实数据采集层 | ✅ | +64 |
| Phase 3 | Writer 竞品报告 | ✅ | +40 |
| Phase 4 | 混合检索(BM25+Dense+Rerank) | ✅ | +67 |
| Phase 5 | 状态治理(Checkpointer+HITL+熔断) | ✅ | +73 |
| Phase 6 | 多租户(Token+限流+加密) | ✅ | +40 |
| Phase 7 | MCP 多元化输出(Notion+飞书) | ✅ | +26 |
| Phase 8 | 量化评测体系(50 条 Benchmark) | ✅ | +56 |
| Phase 9 | 演示材料 + 简历打磨 | 🚧 | — |

详见: [docs/PROJECT_PROGRESS.md](docs/PROJECT_PROGRESS.md)

---

## 开发命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_rate_limiter.py -v

# 跑检索 Benchmark
python -m scripts.run_retrieval_benchmark

# 跑端到端 Benchmark
python -m scripts.run_benchmark

# 配置凭证
python -m scripts.setup_credentials add notion

# 启动服务
uvicorn app.main:app --reload

# Docker Compose
docker-compose up --build
```

---

## 量化指标汇总

### 检索质量
| 指标 | 数值 |
|------|------|
| Recall@5 | 0.933 |
| Rerank Top1 准确率 | 90.0% |
| Avg 延迟 | 0.80ms |
| P95 延迟 | 16.00ms |

### 评测体系
| 指标 | 数值 |
|------|------|
| Benchmark 规模 | 50 条 |
| Tool Call Success | 100% |
| Latency P50 | 2.6s |

### 工程化
| 指标 | 数值 |
|------|------|
| 测试用例 | 388 |
| 测试通过率 | 100% |
| 服务模块 | 20+ |
| LangGraph 节点 | 6 |

---

## 核心亮点

1. **三级降级抓取** — `direct → jina reader → mock`,成功率 95%+
2. **混合检索管道** — BM25 + Dense + 4 信号 Rerank + Jaccard/SimHash 去重
3. **质量门控闭环** — 5 维度评分 + 75 分阈值 + 2 次重试收敛
4. **状态持久化** — Memory/Postgres 双后端 Checkpointer + 断点续跑
5. **Human-in-the-Loop** — `interrupt_before=["publisher"]` + `/resume` 审批端点
6. **三态熔断器** — CLOSED/OPEN/HALF_OPEN,滑动窗口失败率检测
7. **AES-256 凭证加密** — Fernet 对称加密 + 多租户隔离
8. **Token 生命周期管理** — 提前 5 分钟自动刷新 + single-flight
9. **MCP 双通道推送** — Notion + 飞书,凭证脱敏,降级不中断
10. **量化评测体系** — 50 条 Benchmark + 5 大指标 + A/B 框架

详见: [docs/HIGHLIGHTS.md](docs/HIGHLIGHTS.md)

---

## 相关文档

| 文档 | 用途 |
|------|------|
| [PROJECT_PROGRESS.md](docs/PROJECT_PROGRESS.md) | 项目进度追踪 |
| [ARCHITECTURE_DIAGRAM.md](docs/ARCHITECTURE_DIAGRAM.md) | Mermaid 架构图 |
| [HIGHLIGHTS.md](docs/HIGHLIGHTS.md) | 10 大亮点汇总 |
| [EVAL_RESULTS.md](docs/EVAL_RESULTS.md) | 量化评测报告 |
| [EVAL_RESULTS_RETRIEVAL.md](docs/EVAL_RESULTS_RETRIEVAL.md) | 检索评测报告 |
| [ECOMMERCE_DOMAIN_NOTES.md](docs/ECOMMERCE_DOMAIN_NOTES.md) | 7 大电商核心概念 |
| [DEMO_SCENARIOS.md](docs/DEMO_SCENARIOS.md) | 3 个演示场景 |
| [COMPLIANCE_NOTES.md](docs/COMPLIANCE_NOTES.md) | 合规自检清单 |
| [CREDENTIAL_SETUP_GUIDE.md](docs/CREDENTIAL_SETUP_GUIDE.md) | 凭证配置指南 |

---

## 技术栈

- **AI 框架**: LangGraph · LangChain · Pydantic v2
- **Web 框架**: FastAPI · SSE 流式
- **向量数据库**: Qdrant
- **检索算法**: rank_bm25 (BM25Plus) · BGE-style 多信号 Rerank
- **异步**: Asyncio · httpx
- **安全**: cryptography (Fernet AES-128-CBC + HMAC-SHA256)
- **测试**: pytest · pytest-asyncio
- **部署**: Docker · Docker Compose

---

## GitHub

**https://github.com/Sakana-0v0/EcomRadar**

---

**License**: MIT(仅用于个人技术验证,禁止商业化)

**最后更新**: 2026-10-14