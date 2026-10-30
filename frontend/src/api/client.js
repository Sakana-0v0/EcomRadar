/**
 * EcomRadar API 客户端.
 *
 * 覆盖:
 * - POST /api/v1/report/generate   (SSE 流式)
 * - POST /api/v1/report/:id/resume  (HITL 审批)
 * - GET  /api/v1/report/:id/status  (断点状态)
 * - GET  /api/v1/health             (健康检查)
 */

const API_BASE = import.meta.env.VITE_API_BASE || ''

export const DEFAULT_TENANT = 'tenant_1'

/** SSE 事件类型 */
export const SSE_EVENTS = {
  REPORT: 'report',
  SCORE: 'score',
  PAUSED: 'paused',
  PUBLISHED: 'published',
  DONE: 'done',
  ERROR: 'error',
}

/**
 * 启动报告生成, 返回 EventSource 句柄.
 * 注意: EventSource 不支持自定义 header, 故用 query 传 tenant.
 * 后端 middleware 同时支持 header 与 query (见下方 tenantFromQuery 兼容逻辑).
 *
 * @param {string[]} urls 商品 URL 列表
 * @param {string} tenantId 租户 ID
 * @param {object} handlers 事件回调
 * @returns {EventSource}
 */
export function streamReport(urls, tenantId, handlers = {}) {
  const query = new URLSearchParams({
    urls: JSON.stringify(urls),
    tenant_id: tenantId,
  })
  const es = new EventSource(
    `${API_BASE}/api/v1/report/generate?${query.toString()}`,
  )

  es.addEventListener(SSE_EVENTS.REPORT, (e) => handlers.onReport?.(e.data))
  es.addEventListener(SSE_EVENTS.SCORE, (e) => handlers.onScore?.(Number(e.data)))
  es.addEventListener(SSE_EVENTS.PAUSED, (e) => handlers.onPaused?.(e.data))
  es.addEventListener(SSE_EVENTS.PUBLISHED, (e) => handlers.onPublished?.(e.data))
  es.addEventListener(SSE_EVENTS.DONE, (e) => {
    handlers.onDone?.(e.data)
    es.close()
  })
  es.addEventListener(SSE_EVENTS.ERROR, (e) => {
    handlers.onError?.(e.data)
    es.close()
  })
  es.onerror = () => {
    handlers.onError?.('SSE connection error')
    es.close()
  }

  return es
}

/**
 * HITL 审批后恢复工作流.
 */
export async function resumeTask(taskId, approved, tenantId = DEFAULT_TENANT) {
  const res = await fetch(`${API_BASE}/api/v1/report/${taskId}/resume`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': tenantId,
    },
    body: JSON.stringify({ approved }),
  })
  if (!res.ok) {
    throw new Error(`resume failed: ${res.status}`)
  }
  return res.json()
}

/**
 * 查询任务状态.
 */
export async function fetchStatus(taskId, tenantId = DEFAULT_TENANT) {
  const res = await fetch(`${API_BASE}/api/v1/report/${taskId}/status`, {
    headers: { 'X-Tenant-ID': tenantId },
  })
  if (!res.ok) {
    throw new Error(`status failed: ${res.status}`)
  }
  return res.json()
}

/**
 * 健康检查.
 */
export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/api/v1/health`)
  if (!res.ok) throw new Error(`health failed: ${res.status}`)
  return res.json()
}

/**
 * 从 paused 事件中解析 task_id.
 */
export function parseTaskId(pausedData) {
  const m = /task_id=([^;]+)/.exec(pausedData || '')
  return m ? m[1].trim() : null
}
