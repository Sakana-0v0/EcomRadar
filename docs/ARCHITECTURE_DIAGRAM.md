# EcomRadar 架构图

## 1. 全局架构(4 层)

```mermaid
graph TB
    subgraph CLIENT["客户端层"]
        C1["SSE 消费者"]
        C2["HITL 审批端"]
    end

    subgraph MW["中间件层 (FastAPI)"]
        M1["TenantMiddleware<br/>X-Tenant-ID 强校验"]
        M2["RateLimitMiddleware<br/>Sliding Window 10 req/min"]
    end

    subgraph API["API 层"]
        A1["POST /generate<br/>启动 + SSE 推流"]
        A2["POST /:id/resume<br/>HITL 审批后恢复"]
        A3["GET /:id/status<br/>断点状态查询"]
    end

    subgraph AGENT["Agent 状态机层 (LangGraph 6 节点)"]
        N1["Scraper"]
        N2["Extractor"]
        N3["RAG"]
        N4["Writer"]
        N5["Evaluator"]
        N6["Publisher<br/>(HITL 中断点)"]
        N5 -->|"rewrite"| N4
        N4 --> N5
        N5 -->|"publish"| N6
    end

    subgraph SVC["服务层"]
        S1["抓取服务<br/>ecomradar/*"]
        S2["检索服务<br/>retrieval/*"]
        S3["治理服务<br/>governance/*"]
        S4["安全服务<br/>security/*"]
        S5["推送服务<br/>publisher/*"]
    end

    subgraph INF["基础设施"]
        I1["Qdrant<br/>向量数据库"]
        I2["Postgres<br/>Checkpoint"]
        I3["Notion API"]
        I4["飞书 OpenAPI"]
    end

    C1 --> M1
    C2 --> M1
    M1 --> M2
    M2 --> A1
    M2 --> A2
    M2 --> A3
    A1 --> N1
    N1 --> N2 --> N3 --> N4 --> N5
    N5 --> N6
    N1 -.-> S1
    N3 -.-> S2
    N5 -.-> S3
    N6 -.-> S5
    S4 -.-> N6
    S2 -.-> I1
    S3 -.-> I2
    S5 -.-> I3
    S5 -.-> I4
```

---

## 2. 6 节点状态机流转

```mermaid
stateDiagram-v2
    [*] --> Scraper

    Scraper --> Extractor: 抓取完成<br/>(N 个商品)
    Extractor --> RAG: 分块完成<br/>(500~800 tokens)
    RAG --> Writer: 检索完成<br/>(Top-5 上下文)

    Writer --> Evaluator: 报告生成
    Evaluator --> Writer: score < 75<br/>且 retry < 2
    Evaluator --> Publisher: score ≥ 75<br/>(质量达标)
    Evaluator --> [*]: retry ≥ 2<br/>(强制收敛)

    Publisher --> [*]: interrupt 审批<br/>+ 推送完成

    note right of Publisher
        HITL 触发点:
        interrupt_before=["publisher"]
        /resume 端点恢复
    end note
```

---

## 3. 数据流(抓取 → 检索 → 生成)

```mermaid
flowchart LR
    subgraph INPUT["输入"]
        I["商品 URL 列表"]
    end

    subgraph SCRAPE["抓取层"]
        S1["robots.txt 检查"]
        S2["令牌桶限流<br/>≤ 1 req/s"]
        S3["HTTP 抓取<br/>UA 池轮换"]
        S4["jina reader 兜底"]
        S5["mock 数据兜底"]
        S1 --> S2 --> S3
        S3 -.失败.-> S4
        S4 -.失败.-> S5
    end

    subgraph PARSE["解析层"]
        P1["平台识别<br/>jd/tmall/pdd/douyin"]
        P2["字段抽取<br/>标题/价格/SKU/销量"]
        P1 --> P2
    end

    subgraph RETRIEVE["检索层"]
        R1["BM25Plus<br/>关键词召回"]
        R2["Dense 向量召回"]
        R3["加权融合<br/>0.7*Dense + 0.3*BM25"]
        R4["4 信号 Rerank<br/>token/bm25/length/position"]
        R5["元数据过滤"]
        R6["语义去重<br/>Jaccard/SimHash"]
        R1 --> R3
        R2 --> R3
        R3 --> R4 --> R5 --> R6
    end

    subgraph GENERATE["生成层"]
        G1["Writer Node<br/>品牌识别 + 品类推断"]
        G2["LLM 生成<br/>4 段式报告"]
        G3["Evaluator<br/>5 维度评分"]
        G4["75 分门控<br/>retry ≤ 2"]
        G1 --> G2 --> G3 --> G4
    end

    subgraph PUBLISH["推送层"]
        PU1["Markdown → Notion Blocks"]
        PU2["飞书文档创建"]
        PU3["Publisher Node"]
        PU1 --> PU3
        PU2 --> PU3
    end

    I --> S1
    S5 --> P1
    S4 --> P1
    S3 --> P1
    P2 --> R1
    P2 --> R2
    R6 --> G1
    G4 --> PU3
```

---

## 4. 治理机制(可靠性 4 层防护)

```mermaid
graph TB
    subgraph L1["Layer 1: 重试保护"]
        A1["指数退避<br/>base=1s, 2^n"]
        A2["Jitter 扰动<br/>避免惊群"]
        A3["白名单异常<br/>ConnectionError/TimeoutError"]
        A1 --> A2 --> A3
    end

    subgraph L2["Layer 2: 熔断保护"]
        B1["CLOSED<br/>正常通过"]
        B2["OPEN<br/>直接拒绝"]
        B3["HALF_OPEN<br/>探测恢复"]
        B1 -->|"失败率≥50%"| B2
        B2 -->|"timeout 30s"| B3
        B3 -->|"探测成功"| B1
        B3 -->|"探测失败"| B2
    end

    subgraph L3["Layer 3: 限流保护"]
        C1["域名级令牌桶<br/>scraper"]
        C2["租户级 Sliding Window<br/>middleware"]
        C3["单飞 Token 刷新<br/>single-flight"]
        C1 --> C2 --> C3
    end

    subgraph L4["Layer 4: 校验保护"]
        D1["Pydantic Schema 校验"]
        D2["Markdown 章节校验"]
        D3["retry_hint 反馈<br/>引导 LLM 改进"]
        D1 --> D2 --> D3
    end

    L1 --> L2 --> L3 --> L4
```

---

## 5. 检索管道(混合检索)

```mermaid
flowchart TB
    Q["Query"] --> BM["BM25Plus<br/>关键词召回"]
    Q --> DE["Dense 向量召回<br/>余弦相似度"]

    BM --> FU["分数归一化<br/>Min-Max"]
    DE --> FU

    FU --> WE["加权融合<br/>0.7 × Dense<br/>+ 0.3 × BM25"]

    WE --> RR["4 信号 Rerank"]
    RR --> S1["token_overlap 40%<br/>Jaccard 相似度"]
    RR --> S2["bm25_signal 30%<br/>归一化分数"]
    RR --> S3["length_score 20%<br/>长度惩罚"]
    RR --> S4["position_score 10%<br/>位置偏置"]

    S1 --> OUT["Top-K 上下文"]
    S2 --> OUT
    S3 --> OUT
    S4 --> OUT
```

---

## 6. 数据持久化与状态恢复

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API
    participant G as LangGraph
    participant CP as Checkpointer
    participant P as Publisher

    C->>A: POST /generate
    A->>G: astream(initial_state)
    G->>CP: 保存 checkpoint<br/>(每个节点后)
    G->>G: Scraper → Extractor → RAG
    G->>G: Writer → Evaluator
    alt score ≥ 75
        G->>G: interrupt_before publisher
        G-->>A: __interrupt__
        A-->>C: SSE event: paused
        C->>A: POST /:id/resume
        A->>G: astream(None)
        G->>P: 执行 Publisher
        P-->>G: published_channels
        G->>CP: 保存最终 checkpoint
        G-->>C: SSE event: done
    else score < 75
        G->>G: Writer 重试 (≤ 2)
    end

    Note over C,CP: 任何中断后可从最近 checkpoint 恢复
```

---

## 7. 多租户与凭证安全

```mermaid
graph LR
    subgraph REQ["请求"]
        H1["X-Tenant-ID: tenant_1"]
        H2["X-User-ID: user_1"]
    end

    subgraph MWL["中间件链"]
        M1["TenantMiddleware<br/>强校验 + 注入"]
        M2["RateLimitMiddleware<br/>租户级限流"]
    end

    subgraph CRED["凭证层"]
        CR1["CredentialStore<br/>AES-256 加密"]
        CR2["TokenManager<br/>TTL 自动刷新"]
        CR3["_mask_key()<br/>日志脱敏"]
    end

    subgraph DATA["隔离数据"]
        D1["tenant_1<br/>Qdrant payload filter"]
        D2["tenant_2<br/>独立凭证"]
    end

    subgraph PUB["推送"]
        P1["Notion<br/>tenant_1 page"]
        P2["飞书<br/>tenant_1 folder"]
    end

    H1 --> M1
    H2 --> M1
    M1 --> M2
    M2 --> CR1
    CR1 --> CR2
    CR1 --> CR3
    CR1 --> D1
    CR1 --> D2
    CR2 --> P1
    CR2 --> P2
```

---

## 8. 技术栈分布

```mermaid
mindmap
  root((EcomRadar))
    AI框架
      LangGraph
        状态机
        Checkpointer
        interrupt_before
      Pydantic v2
        Schema校验
        Settings
      rank_bm25
        BM25Plus
        中文2-gram
    Web框架
      FastAPI
        Middleware
        Dependency Injection
      SSE
        EventSourceResponse
        event: paused
    存储
      Qdrant
        向量检索
        payload filter
      Postgres
        Checkpoint持久化
        JSONB
    安全
      cryptography
        Fernet
        AES-128-CBC
        HMAC-SHA256
      Token生命周期
        TTL监控
        single-flight
    测试
      pytest
        388 个测试
        100% 通过
      Benchmark
        50 条标注
        5 大指标
```

---

## 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 状态持久化 | LangGraph MemorySaver + 自定义 CheckpointStore | LangGraph 官方接口兼容 + 业务层灵活扩展 |
| 熔断算法 | 滑动窗口失败率 | 相比固定窗口更准确,避免瞬时抖动误触发 |
| 检索融合 | 0.7 Dense + 0.3 BM25 | 偏向语义,兼顾关键词精确匹配 |
| Rerank 信号 | token/bm25/length/position 4 信号 | 轻量级,无需加载 BGE 模型(1GB+) |
| 凭证加密 | Fernet (AES-128-CBC + HMAC) | 工业标准,自带完整性校验 |
| 降级策略 | mock 数据兜底 | 保证演示不中断,失败可审计 |
| HITL 触发 | interrupt_before publisher | 关键外部操作前人工确认 |
| 评测指标 | EM + F1 + ROUGE-L + Latency | 覆盖准确性/相关性/性能 3 维度 |

---

**最后更新**: 2026-10-14
**版本**: Phase 8 完成版
**Commit**: `bd87157`