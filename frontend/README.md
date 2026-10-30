# EcomRadar Dashboard 前端

> React 19 + Vite + Tailwind CSS 3 · 零 UI 框架依赖

## 快速开始

```bash
# 安装依赖
npm install

# 开发模式 (代理到后端 http://localhost:8000)
npm run dev

# 生产构建 (输出到 dist/, FastAPI 自动挂载)
npm run build

# 预览构建产物
npm run preview

# 单元测试
npm run test

# Lint
npm run lint
```

## 组件清单

| 组件 | 文件 | 职责 |
|------|------|------|
| **NodeFlow** | `components/NodeFlow.jsx` | 6 节点状态机流转动画(pulse-ring + flow-dash) |
| **ScorePanel** | `components/ScorePanel.jsx` | 5 维度评分雷达图(SVG) + 权重进度条 |
| **ReportViewer** | `components/ReportViewer.jsx` | 报告预览 + HITL 审批条 + 渲染/源码切换 |
| **Markdown** | `components/Markdown.jsx` | 零依赖 Markdown 渲染器(标题/表格/列表/行内格式) |
| **TenantSwitcher** | `components/TenantSwitcher.jsx` | 多租户切换 + 配额展示 |
| **DegradationTimeline** | `components/DegradationTimeline.jsx` | direct → jina → mock 降级链路可视化 |
| **MetricsPanel** | `components/MetricsPanel.jsx` | 量化指标卡片(Recall@5 / Tool Call / Latency) |
| **EventLog** | `components/MetricsPanel.jsx` | 实时事件流日志 |

## 目录结构

```
frontend/
├── index.html
├── vite.config.js           # dev proxy + vitest 配置
├── tailwind.config.js       # 自定义 radar/ink 色板 + 动画
├── postcss.config.js
└── src/
    ├── main.jsx
    ├── App.jsx               # 主布局 + 状态编排
    ├── index.css             # Tailwind + 组件层 + Markdown 样式
    ├── api/client.js         # SSE + REST 客户端
    ├── components/           # 7 个业务组件
    └── test/                 # 38 个 Vitest 用例
        ├── setup.js
        ├── NodeFlow.test.jsx
        ├── ScorePanel.test.jsx
        ├── Markdown.test.jsx
        └── components.test.jsx
```

## 与后端的集成

### SSE 流(GET 端点)

EventSource 浏览器 API **不支持自定义 header**,因此后端提供 GET 变体:

```
GET /api/v1/report/generate?urls=["https://..."]&tenant_id=tenant_1
```

后端 `TenantMiddleware` 会从 query param 回退读取 `tenant_id`。

### 事件协议

| 事件 | 载荷 | 前端处理 |
|------|------|----------|
| `report` | Markdown 文本 | 追加到报告缓冲区 |
| `score` | 数字(0-100) | 更新评分面板 + 雷达图 |
| `paused` | `task_id=xxx; node=awaiting_human_approval` | 解析 task_id,显示审批条 |
| `published` | `notion,feishu` | 显示推送成功徽章 |
| `done` | task_id | 结束运行状态 |
| `error` | 错误信息 | 红色事件日志 |

### HITL 审批

```js
await resumeTask(taskId, true, tenantId)   // POST /api/v1/report/:id/resume
await resumeTask(taskId, false, tenantId)  // 驳回,跳过发布
```

## 设计系统

**色板** (`tailwind.config.js`):
- `radar-*` — 品牌主色(蓝),用于激活态、链接、强调
- `ink-*` — 中性色阶(深灰蓝),用于深色主题背景与正文

**动画**:
| 动画 | 用途 |
|------|------|
| `pulse-ring` | 激活节点的扩散光环 |
| `flow-dash` | 节点间流动指示点 |
| `slide-up` | 事件日志逐条入场 |
| `fade-in` | 面板淡入 |

## 测试

38 个 Vitest 用例,覆盖:
- NodeFlow — 6 节点渲染 / 状态标记 / 顺序一致性
- ScorePanel — 权重和为 1 / 阈值判断 / 维度标签 / 重试按钮
- Markdown — 标题/段落/粗体/代码/列表/表格/引用/分隔线/完整报告
- ReportViewer — HITL 审批条 / 推送徽章 / 等待态
- TenantSwitcher / DegradationTimeline / MetricsPanel / EventLog
- API 客户端 — task_id 解析 / SSE 事件名

## 后端集成说明

FastAPI 在 `frontend/dist` 存在时自动挂载:
- `GET /` → `index.html`
- `GET /assets/*` → 静态资源
- `GET /api/v1/meta` → 构建信息

未构建时 `GET /` 返回提示 JSON。

---

**版本**: Phase 10 · 2026-10-14
