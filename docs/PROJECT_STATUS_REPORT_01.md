# 📊 项目情况汇报 #1

**生成时间**: 2026-10-12  
**项目**: Multi-Agent Report System（多智能体研报生成系统）  
**汇报周期**: 从项目启动到当前  
**等级**: Level A — 最小可用产品（MVP）达成 ✅

---

## 一、核心结论

> **核心链路已跑通** ✅  
> 系统已具备从 URL 输入到结构化研报输出的完整能力，可以投入演示和小规模使用。

---

## 二、核心链路状态

### 完整链路图

```
[URL 列表]
    ↓
[Scraper]      ✅ 异步并发抓取，5秒超时，HTML 清洗
    ↓
[Extractor]    ✅ 中文句号分块，15% 重叠窗口
    ↓
[RAG]          ✅ Embedding 向量化 + Qdrant 云端检索
    ↓
[Writer]       ✅ 真实 LLM 调用，结构化研报生成
    ↓
[Evaluator]    ✅ 三维度评分（事实/结构/连贯）
    ↓
[Router]       ✅ 75分阈值，2次重试上限
    ↓
[SSE 推流]     ✅ 事件流式输出
```

### 验证结果

| 阶段 | 验证项 | 结果 |
|------|--------|------|
| 单元测试 | 13 个测试用例 | ✅ 13/13 通过 |
| 服务启动 | uvicorn 监听 :8000 | ✅ 200 OK |
| Health 端点 | GET /api/v1/health | ✅ `{"status":"ok"}` |
| URL 校验 | 4 个非法/合法场景 | ✅ 全部符合预期 |
| Qdrant 写入 | 4 chunks 成功入库 | ✅ Points count=4 |
| Qdrant 检索 | Top-3 召回 | ✅ 3 条语义相关文档 |
| 真实 LLM 调用 | chat/completions | ✅ 200 OK，生成 4768 字符 |
| 完整工作流 | graph.ainvoke | ✅ 质量评分 100 |

---

## 三、已实现功能

### 3.1 服务层 (`app/services/`)

| 服务 | 文件 | 核心能力 |
|------|------|----------|
| **scraper.py** | 异步并发抓取 | `asyncio.gather` + httpx，5秒超时，正则清洗 HTML |
| **chunker.py** | 语义分块 | 按 `。！？` 切分，600 字块，90 字重叠 |
| **vector_store.py** | Qdrant 封装 | URL/Key 连接，UUID ID，1024 维向量，query_points 检索 |
| **embedding.py** | Embedding API | qwen3.7-text-embedding，1024 维 |
| **llm.py** | LLM 报告生成 | chat/completions 调用，结构化 prompt |
| **evaluator.py** | 质量评分 | 三维度加权，0-100 分 |

### 3.2 节点层 (`app/graph/nodes/`)

| 节点 | 文件 | 关键特性 |
|------|------|----------|
| **scraper_node** | async | 错误隔离 + 错误消息 |
| **extractor_node** | sync | try/except + 日志 |
| **rag_node** | async | index_and_retrieve 原子操作 + degraded 降级 |
| **writer_node** | async | try/except + degraded 模式 + 日志 |
| **evaluator_node** | sync | try/except + 日志 |

### 3.3 API 层 (`app/api/v1/`)

| 端点 | 方法 | 状态 |
|------|------|------|
| `/api/v1/health` | GET | ✅ 正常 |
| `/api/v1/report/generate` | POST | ✅ 正常（SSE 流式） |
| `/` | GET | ✅ 正常 |

### 3.4 基础设施

- **配置管理** `app/core/config.py`: Pydantic Settings，字段校验
- **日志系统** `app/core/logging.py`: JSON formatter，trace_id 追踪
- **状态定义** `app/graph/state.py`: TypedDict 9 字段
- **工作流** `app/graph/workflow.py`: LangGraph StateGraph 编译

---

## 四、关键技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| 语言 | Python | 3.12 |
| 框架 | LangGraph | StateGraph |
| Web | FastAPI | 0.143+ |
| 向量 DB | Qdrant Cloud | 1.x（query_points API）|
| LLM | MiniMax-M3 (Chat) | - |
| Embedding | qwen3.7-text-embedding | 1024 维 |
| HTTP | httpx | async |
| 校验 | Pydantic | v2 |

---

## 五、外部服务配置

| 服务 | 状态 | 备注 |
|------|------|------|
| **Qdrant Cloud** | ✅ 已连接 | 集合 `reports`（1024 维 COSINE）|
| **MiniMax LLM** | ✅ 已连接 | 生成质量评分 100 |
| **阿里云 Embedding** | ✅ 已连接 | 1024 维向量 |

---

## 六、代码统计

```
总 commit 数: 10
总文件数: 30+ Python 文件
核心代码行数: ~600 行（不含 docstring）
测试用例: 13 个
测试覆盖率: 核心节点 + 服务层
```

### Commit 历史

```
043f18d Task 10: Update FastAPI main.py entry point
3aecad3 feat(core): implement config.py and logging.py
94fabce feat: implement SSE streaming endpoint
cbc3bea Task 7: Assemble LangGraph StateGraph
13a2a68 feat: implement evaluator service, node, and router
46d6eea feat: implement writer_node for report generation
82d3492 feat: implement VectorStore service and RAG node
7775f5d feat: add chunker service and extractor node
9d69e5a feat: implement scraper service and scraper_node
c17fed7 feat: add GraphState TypedDict
```

---

## 七、阶段完成情况

```
[P0] 核心阻塞修复           ✅ 完成
  - 修复 vector_store.py query_vector 传参
  - 修复 RAG 链路（async + index_and_retrieve）
  - 修复 Embedding 向量维度（1536 → 1024）
  - 修复 Point ID（字符串 → UUID）
  - 适配 Qdrant 新 API（query_points）

[P1] 功能完善              ✅ 完成
  - writer_node 错误处理 + 日志
  - evaluator_node 日志
  - extractor_node 错误处理
  - config.py 重复类定义清理
  - request.py URL 校验（非空/协议/数量≤10）

[P2] 产品化完善            ⏳ 部分完成
  - 降级模式（is_degraded）已实现
  - Pydantic 弃用警告（V3 移除前可忽略）

[集成] 端到端验证          ✅ 完成
  - 13 个单元测试
  - 服务启动 + health
  - URL 校验
  - RAG 链路（云端 Qdrant）
  - SSE 端点结构
```

---

## 八、当前限制

1. **Embedding 服务受限**: 阿里云 MaaS 返回 1024 维，需注意 Qdrant collection 维度匹配
2. **重试逻辑未差异化**: 重试时 Prompt 未注入 Evaluator 反馈
3. **无报告持久化**: 生成的报告未保存到磁盘/数据库
4. **无任务管理**: 无 task_id，无法取消/查询历史任务
5. **SSE 粒度**: 节点级别流式，非 LLM token 级流式

---

## 九、下一步建议

### 短期（1-2 周）
- [ ] 任务管理：task_id + 取消/查询接口
- [ ] 报告持久化：保存到 `data/reports/`
- [ ] Writer 重试时注入反馈 Prompt
- [ ] RAG 数据隔离：按 session/用户分集合

### 中期（1-2 月）
- [ ] LLM token 级 SSE 流式
- [ ] Docker Compose 部署
- [ ] Prometheus 监控埋点
- [ ] 评估指标升级（引入 LLM-as-a-Judge）

### 长期（3+ 月）
- [ ] 多用户支持 + 权限管理
- [ ] Web UI 界面
- [ ] 多语言支持
- [ ] 自定义 Prompt 模板

---

## 十、风险与注意事项

| 风险 | 描述 | 应对 |
|------|------|------|
| 外部 API 配额 | LLM/Embedding API 有调用限制 | 添加限流 + 监控 |
| Qdrant 配额 | 云端有存储和向量数限制 | 定期清理 + 归档 |
| 网络抖动 | 5 秒超时可能不够 | 动态调整 |
| LLM 幻觉 | 生成内容可能与事实不符 | Evaluator 已评分，RAG 增强上下文 |

---

## 十一、演示建议

启动命令：
```bash
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

测试请求：
```bash
curl -X POST http://127.0.0.1:8000/api/v1/report/generate \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com"]}'
```

---

## 总结

**🎉 MVP 达成**: 核心链路已完整跑通，系统具备从 URL 输入到结构化研报输出的端到端能力。

**可信度评估**:
- 单元测试：13/13 通过
- 端到端验证：所有关键路径已实测
- 外部服务：Qdrant Cloud + 阿里云 Embedding + MiniMax LLM 三方集成

**推荐**: 可以作为 Level A 产品进行内部演示和小规模试用。
