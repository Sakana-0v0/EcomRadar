/**
 * 报告预览面板 + HITL 审批.
 *
 * 展示 4 段式竞品周报, 并在流程暂停时提供审批按钮.
 */
import { useState } from 'react'
import Markdown from './Markdown'

export default function ReportViewer({
  report,
  paused,
  taskId,
  onApprove,
  onReject,
  publishedChannels = [],
}) {
  const [view, setView] = useState('markdown')

  const sections = report
    ? report.split(/\n(?=#{1,3}\s)/).filter((s) => s.trim())
    : []

  return (
    <div className="panel flex min-h-0 flex-col">
      <div className="panel-header">
        <div className="flex items-center gap-3">
          <span className="panel-title">竞品周报预览</span>
          {publishedChannels.length > 0 && (
            <span className="tag bg-emerald-500/15 text-emerald-300">
              ✓ 已推送 {publishedChannels.join(' / ')}
            </span>
          )}
          {paused && (
            <span className="tag bg-amber-500/15 text-amber-300">⏸ 待审批</span>
          )}
        </div>
        <div className="flex gap-1 rounded-lg bg-ink-900 p-0.5">
          {[
            { k: 'markdown', label: '渲染' },
            { k: 'raw', label: '源码' },
          ].map((t) => (
            <button
              key={t.k}
              type="button"
              onClick={() => setView(t.k)}
              className={`rounded-md px-2.5 py-1 text-xs transition-colors ${
                view === t.k
                  ? 'bg-ink-700 text-white'
                  : 'text-ink-400 hover:text-ink-200'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {paused && (
        <div className="flex flex-wrap items-center gap-3 border-b border-ink-800 bg-amber-500/5 px-4 py-3">
          <div className="flex-1">
            <div className="text-xs font-semibold text-amber-300">
              Human-in-the-Loop: 等待人工审批
            </div>
            <div className="mt-0.5 text-[11px] text-ink-500">
              Publisher 节点前已中断。批准后报告将推送到 Notion / 飞书;驳回则跳过发布。
            </div>
            {taskId && (
              <div className="mt-1 font-mono text-[10px] text-ink-600">task_id = {taskId}</div>
            )}
          </div>
          <button type="button" onClick={onApprove} className="btn-primary">
            ✓ 批准并发布
          </button>
          <button type="button" onClick={onReject} className="btn-danger">
            ✕ 驳回
          </button>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {!report ? (
          <div className="flex h-full min-h-[240px] flex-col items-center justify-center gap-2 text-ink-600">
            <span className="text-3xl">📡</span>
            <span className="text-xs">等待报告生成…</span>
          </div>
        ) : view === 'raw' ? (
          <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-ink-300">
            {report}
          </pre>
        ) : (
          <div className="space-y-1">
            {sections.length > 1 ? (
              <div className="mb-3 flex flex-wrap gap-1.5">
                {sections.map((s, i) => {
                  const m = /^(#{1,3})\s+(.*)/.exec(s)
                  if (!m) return null
                  return (
                    <span
                      key={i}
                      className="tag bg-ink-800 text-ink-400 hover:bg-ink-700 hover:text-ink-200"
                    >
                      {m[2].slice(0, 20)}
                    </span>
                  )
                })}
              </div>
            ) : null}
            <Markdown content={report} />
          </div>
        )}
      </div>
    </div>
  )
}
