/**
 * 6 节点状态机流转图.
 *
 * 节点顺序与后端 app/graph/workflow.py PIPELINE_ORDER 一致:
 * scraper → extractor → rag → writer → evaluator ↻ publisher
 */
import { useEffect, useState } from 'react'

export const NODES = [
  { id: 'scraper', label: 'Scraper', cn: '抓取', desc: '多平台异步采集 + 三级降级' },
  { id: 'extractor', label: 'Extractor', cn: '抽取', desc: '语义分块 + 商品字段解析' },
  { id: 'rag', label: 'RAG', cn: '检索', desc: 'BM25 + Dense + Rerank + Dedup' },
  { id: 'writer', label: 'Writer', cn: '撰写', desc: '4 段式竞品周报生成' },
  { id: 'evaluator', label: 'Evaluator', cn: '评估', desc: '5 维度评分 + 75 分门控' },
  { id: 'publisher', label: 'Publisher', cn: '推送', desc: 'HITL 审批 + Notion/飞书' },
]

const STATUS_STYLE = {
  idle: { ring: 'border-ink-700', bg: 'bg-ink-900', text: 'text-ink-400', dot: 'bg-ink-600' },
  active: {
    ring: 'border-radar-500',
    bg: 'bg-radar-500/10',
    text: 'text-radar-300',
    dot: 'bg-radar-400',
  },
  done: { ring: 'border-emerald-600/60', bg: 'bg-emerald-500/10', text: 'text-emerald-300', dot: 'bg-emerald-500' },
  failed: { ring: 'border-rose-600/60', bg: 'bg-rose-500/10', text: 'text-rose-300', dot: 'bg-rose-500' },
}

export default function NodeFlow({ activeNode, visited = [], failedNode = null, paused = false }) {
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!activeNode) return
    const t = setInterval(() => setTick((v) => v + 1), 1400)
    return () => clearInterval(t)
  }, [activeNode])

  const statusOf = (id) => {
    if (failedNode === id) return 'failed'
    if (activeNode === id) return 'active'
    if (visited.includes(id)) return 'done'
    return 'idle'
  }

  const activeIndex = NODES.findIndex((n) => n.id === activeNode)

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Agent 状态机流转</span>
        <span className="text-xs text-ink-500">
          {paused ? (
            <span className="tag bg-amber-500/15 text-amber-300">⏸ 等待人工审批</span>
          ) : activeNode ? (
            <span className="tag bg-radar-500/15 text-radar-300">● {activeNode}</span>
          ) : (
            <span className="tag bg-ink-800 text-ink-400">待启动</span>
          )}
        </span>
      </div>

      <div className="flex items-stretch gap-0 overflow-x-auto p-4">
        {NODES.map((node, i) => {
          const st = statusOf(node.id)
          const s = STATUS_STYLE[st]
          const isLast = i === NODES.length - 1
          const flowActive = activeIndex >= 0 && i < activeIndex
          const isEvaluator = node.id === 'evaluator'

          return (
            <div key={node.id} className="flex shrink-0 items-center">
              <div className="relative flex w-[136px] flex-col items-center gap-1.5 px-1 text-center">
                {st === 'active' && (
                  <span
                    key={tick}
                    className="absolute inset-x-4 top-4 h-10 animate-pulse-ring rounded-full border border-radar-500/50"
                  />
                )}
                <div
                  className={`relative flex h-10 w-10 items-center justify-center rounded-xl border-2 ${s.ring} ${s.bg} transition-all duration-300`}
                >
                  <span className={`h-2.5 w-2.5 rounded-full ${s.dot} ${st === 'active' ? 'animate-pulse' : ''}`} />
                </div>
                <div className={`text-xs font-semibold ${s.text}`}>{node.label}</div>
                <div className="text-[10px] text-ink-500">{node.cn}</div>
                <div className="px-1 text-[10px] leading-tight text-ink-600">{node.desc}</div>
                {isEvaluator && (
                  <span className="mt-0.5 text-[9px] text-amber-500/80">↺ 重试 ≤ 2</span>
                )}
              </div>

              {!isLast && (
                <div className="relative mx-0.5 h-px w-8 shrink-0 bg-ink-800">
                  <div
                    className={`absolute inset-y-0 left-0 w-1/2 transition-colors duration-500 ${
                      flowActive ? 'bg-radar-500' : 'bg-transparent'
                    }`}
                  />
                  {flowActive && (
                    <span className="absolute -top-1 left-0 h-3 w-3 animate-flow-dash rounded-full bg-radar-400/70" />
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
