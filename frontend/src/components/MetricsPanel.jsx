/**
 * 量化指标面板 + 事件日志.
 *
 * 指标来源:
 * - docs/EVAL_RESULTS.md (端到端评测)
 * - docs/EVAL_RESULTS_RETRIEVAL.md (检索评测)
 */

const METRICS = [
  { label: 'Recall@5', value: '0.933', sub: '混合检索', accent: 'text-radar-300' },
  { label: 'Rerank Top1', value: '90.0%', sub: '4 信号融合', accent: 'text-radar-300' },
  { label: 'Tool Call', value: '100%', sub: '50 条 Benchmark', accent: 'text-emerald-400' },
  { label: 'Latency P50', value: '2.6s', sub: '端到端', accent: 'text-amber-300' },
  { label: 'P95 检索', value: '16ms', sub: '混合检索管道', accent: 'text-ink-200' },
  { label: '测试用例', value: '389', sub: '100% 通过', accent: 'text-ink-200' },
]

export function MetricsPanel() {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">量化指标</span>
        <span className="tag bg-ink-800 text-ink-400">Benchmark v1</span>
      </div>
      <div className="grid grid-cols-2 gap-px bg-ink-800 sm:grid-cols-3">
        {METRICS.map((m) => (
          <div key={m.label} className="bg-ink-900/60 px-3 py-3">
            <div className="text-[10px] text-ink-500">{m.label}</div>
            <div className={`mt-0.5 text-lg font-bold tabular-nums ${m.accent}`}>{m.value}</div>
            <div className="text-[9px] text-ink-600">{m.sub}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function EventLog({ events }) {
  return (
    <div className="panel flex min-h-0 flex-col">
      <div className="panel-header">
        <span className="panel-title">事件流</span>
        <span className="tag bg-ink-800 text-ink-400">{events.length} 条</span>
      </div>
      <div className="max-h-[220px] min-h-0 flex-1 overflow-y-auto p-2">
        {events.length === 0 ? (
          <div className="py-6 text-center text-[11px] text-ink-600">暂无事件</div>
        ) : (
          events.map((e, i) => (
            <div
              key={i}
              className="flex animate-slide-up items-start gap-2 rounded px-2 py-1 text-[11px] hover:bg-ink-800/40"
            >
              <span className="mt-0.5 shrink-0 font-mono text-[9px] text-ink-600">
                {e.ts}
              </span>
              <span
                className={`shrink-0 rounded px-1.5 py-0.5 text-[9px] font-medium ${
                  e.kind === 'error'
                    ? 'bg-rose-500/15 text-rose-300'
                    : e.kind === 'success'
                      ? 'bg-emerald-500/15 text-emerald-300'
                      : e.kind === 'warn'
                        ? 'bg-amber-500/15 text-amber-300'
                        : 'bg-radar-500/15 text-radar-300'
                }`}
              >
                {e.kind}
              </span>
              <span className="min-w-0 flex-1 break-words text-ink-300">{e.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
